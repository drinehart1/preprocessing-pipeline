import argparse
import os, sys
import pandas as pd
import numpy as np
import cv2
import ast
from skimage import io
from tqdm import tqdm
from collections import defaultdict

HOME = os.path.expanduser("~")
PATH = os.path.join(HOME, 'programming/pipeline_utility')
CSV_PATH = '/net/birdstore/Active_Atlas_Data/data_root/atlas_data/foundation_brain_annotations'
sys.path.append(PATH)
from utilities.contour_utilities import get_contours_from_annotations
from utilities.file_location import FileLocationManager

def make_annotations(animal):

    csvfile = os.path.join(CSV_PATH, f'{animal}_annotation.csv')
    hand_annotations = pd.read_csv(csvfile)
    hand_annotations['vertices'] = hand_annotations['vertices'] \
        .apply(lambda x: x.replace(' ', ','))\
        .apply(lambda x: x.replace('\n',','))\
        .apply(lambda x: x.replace(',]',']'))\
        .apply(lambda x: x.replace(',,', ','))\
        .apply(lambda x: x.replace(',,', ','))\
        .apply(lambda x: x.replace(',,', ',')).apply(lambda x: x.replace(',,', ','))

    hand_annotations['vertices'] = hand_annotations['vertices'].apply(lambda x: ast.literal_eval(x))


    structures = list(hand_annotations['name'].unique())
    section_structure_vertices = defaultdict(dict)
    for structure in tqdm(structures):
        contour_annotations, first_sec, last_sec = get_contours_from_annotations(animal, structure, hand_annotations, densify=4)
        for section in contour_annotations:
            section_structure_vertices[section][structure] = contour_annotations[section][structure][1]

    fileLocationManager = FileLocationManager(animal)
    section_images = {}
    thumbnail_dir = os.path.join(fileLocationManager.prep, 'CH1', 'thumbnail')
    for file_name in tqdm(sorted(os.listdir(thumbnail_dir))):
        filepath = os.path.join(thumbnail_dir, file_name)
        img = io.imread(filepath)
        section = int(file_name.split('.')[0])

        for structure in section_structure_vertices[section]:
            pts = section_structure_vertices[section][structure]
            points = np.array(pts, dtype=np.int32)
            points = points // 32
            cv2.polylines(img, [points], isClosed=True, color=(0, 0, 0), thickness=2)

        section_images[section] = img


    OUTPUT = os.path.join(fileLocationManager.prep, 'CH1', 'annotations')
    os.makedirs(OUTPUT, exist_ok=True)
    for section in tqdm(section_images):
        outpath = os.path.join(OUTPUT, str(section).zfill(3) + '.tif')
        cv2.imwrite(outpath, section_images[section])



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Work on Animal')
    parser.add_argument('--animal', help='Enter the animal', required=True)

    args = parser.parse_args()
    animal = args.animal
    make_annotations(animal)