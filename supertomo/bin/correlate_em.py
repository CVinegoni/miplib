#!/usr/bin/env python

"""
fusion_main.py

Copyright (c) 2014 Sami Koho  All rights reserved.

This software may be modified and distributed under the terms
of the BSD license.  See the LICENSE file for details.
"""

import os
import sys
import datetime
import SimpleITK as sitk

from supertomo.reconstruction import registration
from supertomo.io import utils as ioutils
from supertomo.utils import itkutils
from supertomo.ui import arguments


def check_necessary_inputs(options):

    if options.sted_image_path is None:
        print "EM image not specified"
        return False

    if options.em_image_path is None:
        print "STED image not specified"
        return False

    if not (options.register or options.transform):
        print "You must specify an operation --register or --transform"
        return False

    return True


def main():
    options = arguments.get_correlate_tem_script_options(sys.argv[2:])
    
    # SETUP
    ##########################################################################
    # Check that all the necessary inputs are given
    if not check_necessary_inputs(options):
        sys.exit(1)
        
    # Check that the STED image exists
    options.sted_image_path = os.path.join(options.working_directory,
                                         options.sted_image_path)
    if not os.path.isfile(options.sted_image_path):
        print 'No such file: %s' % options.sted_image_path
        sys.exit(1)

    # Check that the EM image exists
    options.em_image_path = os.path.join(options.working_directory,
                                           options.em_image_path)
    if not os.path.isfile(options.em_image_path):
        print 'No such file: %s' % options.em_image_path
        sys.exit(1)

    # Output directory name will be automatically formatted according
    # to current date and time; e.g. 2014-02-18_supertomo_output
    output_dir = datetime.datetime.now().strftime("%Y-%m-%d")+'_clem_output'
    output_dir = os.path.join(options.working_directory, output_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Load input images
    sted_image = ioutils.get_itk_image(options.sted_image_path, convert_numpy=False)
    em_image = ioutils.get_itk_image(options.em_image_path, convert_numpy=False)
    
    # PRE-PROCESSING
    ##########################################################################
    # Save originals for possible later use
    sted_original = sted_image
    em_original = em_image

    if options.dilation_size != 0:
        print 'Degrading input images with Dilation filter'
        sted_image = itkutils.grayscale_dilate_filter(
            sted_image,
            options.dilation_size
        )
        em_image = itkutils.grayscale_dilate_filter(
            em_image,
            options.dilation_size
        )

    if options.gaussian_variance != 0.0:
        print 'Degrading the EM image with Gaussian blur filter'

        em_image = itkutils.gaussian_blurring_filter(
            em_image,
            options.gaussian_variance
        )
    if options.mean_kernel != 0:
        sted_image = itkutils.mean_filter(
            sted_image,
            options.mean_kernel
        )
        em_image = itkutils.mean_filter(
            em_image,
            options.mean_kernel
        )
    #todo: convert the pixel type into a PixelID enum
    if options.use_internal_type:

        sted_image = itkutils.type_cast(
            sted_image,
            options.image_type
        )
        em_image = itkutils.type_cast(
            em_image,
            options.image_type
         )

    if options.threshold > 0:
        sted_image = itkutils.threshold_image_filter(
            sted_image,
            options.threshold
        )

        em_image = itkutils.threshold_image_filter(
            em_image,
            options.threshold
        )

    if options.normalize:
        print 'Normalizing images'

        # Normalize
        sted_image = itkutils.normalize_image_filter(sted_image)
        em_image = itkutils.normalize_image_filter(em_image)

        if options.rescale_to_full_range:
            sted_image = itkutils.rescale_intensity(sted_image)
            em_image = itkutils.rescale_intensity(em_image)
    
    # REGISTRATION
    ##########################################################################
    if options.register:

        final_transform = registration.itk_registration_2d(sted_image, em_image, options)

        em_image = itkutils.resample_image(
            em_original,
            final_transform,
            reference=sted_image
        )

    # TRANSFORM
    ##########################################################################
    if options.transform:

        transform_path = os.path.join(options.working_directory,
                                      options.transform_path)
        if not os.path.isfile(transform_path):
            raise ValueError('Not a valid file %s' % transform_path)

        transform = sitk.ReadTransform(transform_path)

        em_image = itkutils.resample_image(
            em_original,
            transform,
            reference=sted_image
        )

    # OUTPUT
    ##########################################################################

    # Files are named according to current time (the date will be
    # in the folder name)
    date_now = datetime.datetime.now().strftime("%H-%M-%S")
    file_name = ''

    if options.transform:
        file_name = date_now + '-clem_transform.tiff'

    elif options.register:
        tfm_name = os.path.join(output_dir, date_now + '_transform' + '.txt')
        sitk.WriteTransform(final_transform, tfm_name)

        file_name = date_now + \
                    '-clem_registration-' + \
                    options.registration_method + \
                    '.tiff'

    file_name = os.path.join(output_dir, file_name)

    rgb_image = sitk.Compose((sted_original, em_image))
    sitk.WriteImage(rgb_image, file_name)


if __name__ == "__main__":
    main()




