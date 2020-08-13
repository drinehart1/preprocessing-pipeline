"""
This is for cleaning/masking channel 2 and channel 3 from the mask created
on channel 1. It works on channel one also, but since that is already cleaned and
normalized, it will just to the rotation and flip
"""
import argparse
import os

import cv2
import numpy as np
from skimage import io
from tqdm import tqdm

from sql_setup import CLEAN_CHANNEL_1_THUMBNAIL_WITH_MASK, CLEAN_CHANNEL_1_FULL_RES_WITH_MASK, \
    CLEAN_CHANNEL_2_FULL_RES_WITH_MASK, CLEAN_CHANNEL_3_FULL_RES_WITH_MASK
from utilities.alignment_utility import get_last_2d, SCALING_FACTOR
from utilities.file_location import FileLocationManager
from utilities.logger import get_logger
from utilities.sqlcontroller import SqlController
from utilities.utilities_mask import rotate_image, place_image, linnorm


def fix_ntb(infile, mask, logger, rotation, flip):
    try:
        img = io.imread(infile)
    except:
        logger.warning(f'Could not open {infile}')
    img = get_last_2d(img)
    fixed = cv2.bitwise_and(img, img, mask=mask)

    if rotation > 0:
        fixed = rotate_image(fixed, infile, rotation)

    if flip == 'flip':
        fixed = np.flip(fixed)
    if flip == 'flop':
        fixed = np.flip(fixed, axis=1)

    if channel == 1:
        clahe = cv2.createCLAHE(clipLimit=40.0, tileGridSize=(12, 12))
        fixed = clahe.apply(fixed.astype(np.uint16))

    return fixed


def fix_thion(infile, mask, logger, rotation, flip):

    img_ch1 = imgfull[:, :, 0]
    img_ch2 = imgfull[:, :, 1]
    img_ch3 = imgfull[:, :, 2]
    fixed1 = cv2.bitwise_and(img_ch1, img_ch1, mask=mask)
    fixed2 = cv2.bitwise_and(img_ch2, img_ch2, mask=mask)
    fixed3 = cv2.bitwise_and(img_ch3, img_ch3, mask=mask)

    if rotation > 0:
        fixed1 = rotate_image(fixed1, infile, rotation)
        fixed2 = rotate_image(fixed2, infile, rotation)
        fixed3 = rotate_image(fixed3, infile, rotation)

    if flip == 'flip':
        fixed1 = np.flip(fixed1)
        fixed2 = np.flip(fixed2)
        fixed3 = np.flip(fixed3)
    if flip == 'flop':
        fixed1 = np.flip(fixed1, axis=1)
        fixed2 = np.flip(fixed2, axis=1)
        fixed3 = np.flip(fixed3, axis=1)

    fixed = np.dstack((fixed1, fixed2, fixed3))
    #fixed = fixed3
    return fixed


def masker(animal):
    logger = get_logger(animal)
    sqlController = SqlController(animal)
    fileLocationManager = FileLocationManager(animal)
    PADDED = os.path.join(fileLocationManager.prep, 'CH1', 'thumbnail_padded')
    INPUT = os.path.join(fileLocationManager.prep, 'CH1', 'thumbnail')
    width = sqlController.scan_run.width
    height = sqlController.scan_run.height
    max_width = int(width * SCALING_FACTOR)
    max_height = int(height * SCALING_FACTOR)
    bgcolor = 0
    dt = 'uint16'
    stain = sqlController.histology.counterstain

    if 'thion' in stain.lower():
        bgcolor = 255
        dt = 'uint8'

    files = sorted(os.listdir(INPUT))

    for i, file in enumerate(tqdm(files)):
        infile = os.path.join(INPUT, file)
        outpath = os.path.join(PADDED, file)
        if os.path.exists(outpath):
            continue
        try:
            src = cv2.imread(infile)
        except:
            logger.warning(f'Could not open {infile}')
        fixed = place_image(src, file, max_width, max_height, bgcolor)

        cv2.imwrite(outpath, fixed.astype(dt))
    print('Finished')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Work on Animal')
    parser.add_argument('--animal', help='Enter the animal', required=True)
    args = parser.parse_args()
    animal = args.animal
    masker(animal)
