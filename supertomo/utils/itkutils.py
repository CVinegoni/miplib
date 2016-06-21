"""
itkutils.py

Copyright (C) 2014 Sami Koho
All rights reserved.

This software may be modified and distributed under the terms
of the BSD license.  See the LICENSE file for details.

This file contains several utilities & filters for simplified
usage of ITK (www.itk.org) modules in Python. Most of the ITK classes
have been implemented in similar manner, so it should be rather
easy to include additional filters.

"""
import SimpleITK as sitk
import numpy
import scipy

def convert_to_numpy(itk_image):
    """
    A simple conversion function from ITK:Image to a Numpy array. Please notice
    that the pixel size information gets lost in the conversion. If you want
    to conserve image information, rather use ImageStack class method in
    iocbio.io.image_stack module
    """
    assert isinstance(itk_image, sitk.Image)
    array = sitk.GetArrayFromImage(image)
    # In ITK the order of the dimensions differs from Numpy. The array conversion
    # re-orders the dimensions, but of course the same has to be done to the spacing
    # information.
    spacing_orig = image.GetSpacing()[::-1]
    spacing = tuple(dim / scale_c for dim in spacing_orig)

    return array, spacing


def convert_from_numpy(array, spacing):
    assert isinstance(array, numpy.ndarray)
    image = sitk.GetImageFromArray(array)
    image.SetSpacing(spacing[::-1])

    return image


def make_itk_transform(type, dims, parameters, fixed_parameters):
    """
    A function that can be used to construct a ITK spatial transform from
    known transform parameters.
    :param transform_type:      A string that exactly matches the ITK transform
                                type, eg "VerorRigid3DTransform"
    :param parameters:          The transform parameters tuple
    :param fixed_parameters:    The transform fixed parameters tuple
    :return:                    Returns an initialized ITK spatial transform.
    """
    transform = sitk.Transform(dims, type)

    transform.SetParameters(parameters)
    transform.SetFixedParameters(fixed_parameters)

    return transform



def resample_image(image, transform, reference=None):
    """
    Resampling filter for manipulating data volumes. This function can be
    used to transform an image module or to perform up or down sampling
    for example.

    image       =   input image object itk::Image
    transform   =   desired transform itk::Transform
    image_type  =   pixel type of the image data
    reference   =   a reference image, which can be used in resizing
                    applications, when different dimensions and or
                    spacing are desired to the output image
    """
    assert isinstance(image, sitk.Image)
    if reference is None:
        reference = image
    resampler = sitk.ResampleImageFilter()
    resampler.SetTransform(transform)

    resampler.SetInterpolator(sitk.sitkLinear)

    resampler.SetSize(reference.GetSize())
    resampler.SetOutputOrigin(reference.GetOrigin())
    resampler.SetOutputSpacing(reference.GetSpacing())
    resampler.SetOutputDirection(reference.GetDirection())
    resampler.SetDefaultPixelValue(0)

    return resampler.Execute(image)


def rotate_psf(psf, transform, spacing=None, return_numpy=False):
    """
    In case, only one point-spread-function (PSF) is to be used in the image
    fusion, it needs to be rotated with the transform of the moving_image.
    The transform is generated during the registration process.

    psf             = A Numpy array, containing PSF data
    transform       = itk::VersorRigid3DTransform object
    return_numpy    = it is possible to either return the result as an
                      itk:Image, or a ImageStack.

    """
    assert isinstance(transform, sitk.VersorRigid3DTransform)

    if isinstance(psf, numpy.ndarray):
        image = convert_from_numpy(psf, spacing)
    else:
        image = psf

    assert isinstance(image, sitk.Image)

    # We don't want to translate, but only rotate
    parameters = transform.GetParameters()
    for i in range(3, 6):
        parameters[i] = 0.0
    transform.SetParameters(parameters)

    # Find  and set center of rotation This assumes that the PSF is in
    # the centre of the volume, which should be expected, as otherwise it
    # will cause translation of details in the final image.
    imdims = image.GetSize()
    imspacing = image.GetSpacing()

    center = map(
        lambda size, spacing: spacing * size / 2, imdims, imspacing
    )

    transform.SetFixedParameters(center)

    # Rotate
    image = resample_image(image, transform)

    if return_numpy:
        return convert_to_numpy(image)
    else:
        return image


def resample_to_isotropic(itk_image):
    """
    This function can be used to rescale or upsample a confocal stack,
    which generally has a larger spacing in the z direction.

    :param itk_image:   an ITK:Image object
    :param image_type:  an ITK image type string (e.g. 'IUC3')
    :return:            returns a new ITK:Image object with rescaled
                        axial dimension
    """
    assert isinstance(itk_image, sitk.Image)

    method = sitk.ResampleImageFilter()
    transform = sitk.Transform()
    transform.SetIdentity()

    method.SetInterpolator(sitk.sitkBSpline)
    method.SetDefaultPixelValue(0)

    # Set output spacing
    spacing = itk_image.GetSpacing()

    if len(spacing) != 3:
        print "The function resample_to_isotropic(itk_image, image_type) is" \
              "intended for processing 3D images. The input image has %d " \
              "dimensions" % len(spacing)
        return

    scaling = spacing[2]/spacing[0]

    spacing[:] = spacing[0]
        
    method.SetOutputSpacing(spacing)
    method.SetOutputDirection(itk_image.GetDirection())
    method.SetOutputOrigin(itk_image.GetOrigin())

    # Set Output Image Size
    region = itk_image.GetLargestPossibleRegion()
    size = region.GetSize()
    size[2] = int(size[2]*scaling)
    method.SetSize(size)

    transform.SetIdentity()
    method.SetTransform(transform)

    return method.Execute(itk_image)


def rescale_intensity(image):
    """
    A filter to scale the intensities of the input image to the full range
    allowed by the pixel type

    Inputs:
        image       = an itk.Image() object
        input_type  = pixel type string of the input image. Must be an ITK
                      recognized pixel type
        output_type = same as above, for the output image
    """
    assert isinstance(image, sitk.Image)
    method = sitk.RescaleIntensityImageFilter()
    image_type = image.GetPixelIDTypeAsString()
    if image_type == '8-bit unsigned integer':
        method.SetOutputMinimum(0)
        method.SetOutputMaximum(255)
    else:    
        print "The rescale intensity filter has not been implemented for ", image_type
        return image
    
    # TODO: Add pixel type check that is needed to check the bounds of re-scaling
    return method.Execute(image)


def gaussian_blurring_filter(image, variance):
    """
    Gaussian blur filter
    """

    filter = sitk.DiscreteGaussianImageFilter()
    filter.SetVariance(variance)

    return filter.Execute(image)


def grayscale_dilate_filter(image, kernel_radius):
    """
    Grayscale dilation filter
    """

    method = sitk.GrayscaleDilateImageFilter()
    kernel = method.GetKernel()
    kernel.SetKernelRadius(kernel_radius)
    kernel = kernel.Ball(kernel.GetRadius())
    method.SetKernel(kernel)

    return method.Execute(image)


def mean_filter(image, kernel_radius):
    """
    Uniform Mean filter for itk.Image objects
    """
    method = sitk.MeanImageFilter()
    method.SetRadius(kernel_radius)

    return method.Execute(image)


def median_filter(image, kernel_radius):
    """
    Median filter for itk.Image objects

    :param image:           an itk.Image object
    :param image_type:      image type string (e.g. IUC2, IF3)
    :param kernel_radius:   median kernel radius
    :return:                filtered image
    """
    method = sitk.MedianImageFilter
    method.SetRadius(kernel_radius)

    return method.Execute(image)


def normalize_image_filter(image):
    """
    Normalizes the pixel values in an image to Mean of zero and Variance
    of one. A floating point image_type is expected. For integer pixel
    type, casting to a float is recommended before using this.
    """

    method = sitk.NormalizeImageFilter()
    return method.Execute(image)


def threshold_image_filter(image, threshold, th_value=0,
                           th_method="below"):
    """
    Thresholds an image by setting pixel values above or below "threshold"
    to "th_value". The result is not a binary image, but a thresholded
    grayscale image.
    """

    method = sitk.ThresholdImageFilter()
    if th_method is "above":
        method.SetLower(threshold)
    elif th_method is "below":
        method.SetUpper(threshold)

    method.SetOutsideValue(th_value)

    return method.Execute(image)


def get_image_statistics(image):
    """
    A utility to calculate basic image statistics (Mean and Variance here)

    :param image:       an ITK:Image object
    :param image_type:  a string describing the image type (e.g. IUC3). The
                        naming convention as in ITK
    :param verbal:      print results on screen (ON/OFF)
    :return:            returns the image mean and variance in a tuple
    """
    method = sitk.StatisticsImageFilter()
    method.Execute(image)
    mean = method.GetMean()
    variance = method.GetVariance()
    max = method.GetMaximum()
    min = method.GetMinimum()

    return mean, variance, min, max


def type_cast(image, output_type):
    """
    A utility for changing the image pixel container type

    :param image:       An ITK:Image
    :param output_type: output image type as ITK PixelID
    :return:            returns the image with new pixel type
    """
    assert isinstance(image, sitk.Image)

    method = sitk.CastImageFilter()
    method.SetOutputPixelType(output_type)

    return method.Execute(image)


def calculate_center_of_image(image, center_of_mass=False):
    """
    Center of an image can be defined either geometrically or statistically,
    as a Center-of-Gravity measure.

    This was originally Based on itk::ImageMomentsCalculator
    http://www.itk.org/Doxygen/html/classitk_1_1ImageMomentsCalculator.html

    However that filter is not currently implemented in SimpleITK and therefore
    a Numpy approach is used.
    """
    assert isinstance(image, sitk.Image)

    imdims = image.GetSize()
    imspacing = image.GetSpacing()

    if center_of_mass:
        np_image, spacing = convert_to_numpy(image)
        center = scipy.ndimage.measurements.center_of_mass(np_image)
        center *= spacing
    else:
        center = map(
            lambda size, spacing: spacing * size / 2,
            imdims, imspacing
        )
    return center


def make_composite_rgb_image(red, green, blue=None):
    """
    A utitity to combine two or threegrayscale images into a single RGB image.
    If only two images are provided, an empty image is placed in the blue
    channel.

    :param red:  Red channel image. All the images should be sitk.Image
                 objects
    :param green Green channel image
    :param blue: Blue channel image.
    :return:     Returns a RGB composite image.
    """
    assert isinstance(red, sitk.Image) and isinstance(green, sitk.Image)
    red = sitk.Cast(red, sitk.sitkUInt8)
    green = sitk.Cast(green, sitk.sitkUInt8)
    if blue is not None:
        assert isinstance(blue, sitk.Image)
        blue = sitk.Cast(blue, sitk.sitkUInt8)

        return sitk.Compose(red, green, blue)
    else:
        blue = sitk.Image(red.GetSize(), sitk.sitkUInt8)
        blue.CopyInformation(red)
        return sitk.Compose(red, green, blue)


























