import pickle
from os.path import expanduser
from tqdm import tqdm
HOME = expanduser("~")
import os, sys
import numpy as np
from collections import OrderedDict
from shutil import move
import subprocess

sys.path.append(os.path.join(os.getcwd(), '../'))

from utilities.sqlcontroller import SqlController
from utilities.utilities_registration import create_warp_transforms, register_correlation
from utilities.alignment_utility import SCALING_FACTOR
from utilities.file_location import FileLocationManager


animal = 'DK39'
fileLocationManager = FileLocationManager(animal)
sqlController = SqlController(animal)

# define variables
INPUT = os.path.join(fileLocationManager.prep, 'CH1', 'thumbnail_cleaned')
ALIGNED = os.path.join(fileLocationManager.prep, 'CH1', 'thumbnail_aligned')
resolution = 'thumbnail'
width = sqlController.scan_run.width
height = sqlController.scan_run.height
max_width = int(width * SCALING_FACTOR)
max_height = int(height * SCALING_FACTOR)
bgcolor = 'black' # this should be black, but white lets you see the rotation and shift
ITERATIONS = 8

rotations = OrderedDict()


for repeats in range(0, ITERATIONS):
    transformation_to_previous_section = OrderedDict()

    files = sorted(os.listdir(INPUT))

    for i in tqdm(range(1, len(files))):
        fixed_index = str(i - 1).zfill(3)
        moving_index = str(i).zfill(3)

        R,t = register_correlation(INPUT, fixed_index, moving_index)
        T = np.vstack([np.column_stack([R, t]), [0, 0, 1]])
        transformation_to_previous_section[files[i]] = T

        if repeats == 0:
            rotations[files[i]] = T
        else:
            ##### CHECK, are the two lines below correct? I'm multiplying the rotation matrix and adding the
            ##### translation vectors
            #### Check 2, just multiplying the entire matrix 
            rotations[files[i]] = rotations[files[i]] @ T



    ##### This block of code is from Yuncong so I didn't write it.
    anchor_index = len(files) // 2 # middle section of the brain
    transformation_to_anchor_section = {}
    # Converts every transformation
    for moving_index in range(len(files)):
        if moving_index == anchor_index:
            transformation_to_anchor_section[files[moving_index]] = np.eye(3)
        elif moving_index < anchor_index:
            T_composed = np.eye(3)
            for i in range(anchor_index, moving_index, -1):
                T_composed = np.dot(np.linalg.inv(transformation_to_previous_section[files[i]]), T_composed)
            transformation_to_anchor_section[files[moving_index]] = T_composed
        else:
            T_composed = np.eye(3)
            for i in range(anchor_index + 1, moving_index + 1):
                T_composed = np.dot(transformation_to_previous_section[files[i]], T_composed)
            transformation_to_anchor_section[files[moving_index]] = T_composed

    # scale the translations to either the thumbnail or the full resolution sized images
    warp_transforms = create_warp_transforms(animal, transformation_to_anchor_section, 'thumbnail', resolution)
    ordered_transforms = OrderedDict(sorted(warp_transforms.items()))
    for file, arr in tqdm(ordered_transforms.items()):
        T = np.linalg.inv(arr)
        sx = T[0, 0]
        sy = T[1, 1]
        rx = T[1, 0]
        ry = T[0, 1]
        tx = T[0, 2]
        ty = T[1, 2]
        # sx, rx, ry, sy, tx, ty
        op_str = f" +distort AffineProjection '{sx},{rx},{ry},{sy},{tx},{ty}'"
        op_str += f' -crop {max_width}x{max_height}+0.0+0.0!'
        input_fp = os.path.join(INPUT, file)
        output_fp = os.path.join(ALIGNED, file)
        if os.path.exists(output_fp):
            continue

        cmd = f"convert {input_fp} -depth 16 +repage -virtual-pixel background -background {bgcolor} {op_str} -flatten -compress lzw {output_fp}"
        subprocess.run(cmd, shell=True)

    ## move aligned images to cleaned and repeat loop
    if repeats < ITERATIONS - 1:
        for file in os.listdir(INPUT):
            filepath = os.path.join(INPUT, file)
            os.unlink(filepath)
        for file in files:
            move(os.path.join(ALIGNED, file), INPUT)

# Store data (serialize)
rotation_storage = os.path.join(fileLocationManager.elastix_dir, 'rotations.pickle')
with open(rotation_storage, 'wb') as handle:
    pickle.dump(rotations, handle)
