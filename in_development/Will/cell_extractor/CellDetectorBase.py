import os
from time import time
import glob
from Brain import Brain
import pickle as pkl
import pandas as pd
import numpy as np
from cell_extractor.DetectionPlotter import DetectionPlotter

class CellDetectorBase(Brain):
    def __init__(self,animal,section = 0):
        self.attribute_functions = dict(
            tile_origins = self.get_tile_origins)
        super().__init__(animal)
        self.plotter = DetectionPlotter()
        self.ncol = 2
        self.nrow = 5
        self.section = section
        self.DATA_PATH = "/data/cell_segmentation/"
        self.ANIMAL_PATH = os.path.join(self.DATA_PATH,self.animal)
        self.AVERAGE_CELL_IMAGE_DIR = os.path.join(self.ANIMAL_PATH,'average_cell_image.pkl')
        self.TILE_INFO_DIR = os.path.join(self.ANIMAL_PATH,'tile_info.csv')
        os.makedirs(self.ANIMAL_PATH,exist_ok = True)
        self.CH3 = os.path.join(self.ANIMAL_PATH,"CH3")
        self.CH1 = os.path.join(self.ANIMAL_PATH,"CH1")
        self.CH3_SECTION_DIR=os.path.join(self.CH3,f"{self.section:03}")
        self.CH1_SECTION_DIR=os.path.join(self.CH1,f"{self.section:03}")
        if hasattr(self, 'version'):
            csv_name = 'detections_'+self.animal+'.'+str(self.version)+'.csv'
            self.DETECTION_RESULT_DIR = os.path.join(self.ANIMAL_PATH,csv_name)
        self.CLASSIFIER_PATH = os.path.join(self.DATA_PATH,'BoostedTrees.pkl')
        self.get_tile_and_image_dimensions()
        self.get_tile_origins()
        self.check_tile_information()
    
    def get_tile_information(self):
        self.check_attributes(['tile_origins'])
        ntiles = len(self.tile_origins)
        tile_information = pd.DataFrame(columns = ['id','tile_origin','ncol','nrow','width','height'])
        for tilei in range(ntiles):
            tile_informationi = dict(
                id = tilei,
                tile_origin = self.tile_origins[tilei],
                ncol = self.ncol,
                nrow = self.nrow,
                width = self.width,
                height = self.height) 
            tile_information = tile_information.append(tile_informationi,ignore_index=True)
        return tile_information
    
    def save_tile_information(self):
        tile_information = self.get_tile_information()
        try:
            tile_information.to_csv(self.TILE_INFO_DIR,index = False)
        except IOError as e:
            print(e)
    
    def check_tile_information(self):
        if os.path.exists(self.TILE_INFO_DIR):
            tile_information = pd.read_csv(self.TILE_INFO_DIR)
            tile_information.tile_origin = tile_information.tile_origin.apply(eval)
            assert (tile_information == self.get_tile_information()).all().all()
        else:
            self.save_tile_information()
        
    def get_tile_and_image_dimensions(self):
        self.width,self.height = self.get_image_dimension()
        self.tile_height = int(self.height / self.nrow )
        self.tile_width=int(self.width/self.ncol )
    
    def get_tile_origins(self):
        self.check_attributes(['width'])
        self.tile_origins={}
        for i in range(self.nrow*self.ncol):
            row=int(i/self.ncol)
            col=i%self.ncol
            self.tile_origins[i] = (row*self.tile_height,col*self.tile_width)

    def get_tile_origin(self,tilei):
        self.check_attributes(['tile_origins'])
        return np.array(self.tile_origins[tilei],dtype=np.int32)
    
    def get_sections_with_string(self,search_string):
        sections = os.listdir(self.CH3)
        sections_with_string = []
        for sectioni in sections:
            if glob.glob(os.path.join(self.CH3,sectioni,search_string)):
                sections_with_string.append(int(sectioni))
        return sections_with_string

    def get_sections_without_string(self,search_string):
        sections = os.listdir(self.CH3)
        sections_with_string = []
        for sectioni in sections:
            if not glob.glob(os.path.join(self.CH3,sectioni,search_string)):
                sections_with_string.append(int(sectioni))
        return sections_with_string

    def get_sections_with_csv(self):
        return self.get_sections_with_string('*.csv')
    
    def get_sections_without_csv(self):
        return self.get_sections_without_string('*.csv')

    def get_sections_with_example(self):
        return self.get_sections_with_string('extracted_cells*')

    def get_sections_without_example(self):
        return self.get_sections_without_string('extracted_cells*')
    
    def get_sections_with_features(self):
        return self.get_sections_with_string('puntas_*')

    def get_sections_without_features(self):
        return self.get_sections_without_string('puntas_*')

    def get_example_save_path(self):
        return self.CH3_SECTION_DIR+f'/extracted_cells_{self.section}.pkl'
    
    def get_feature_save_path(self):
        return self.CH3_SECTION_DIR+f'/puntas_{self.section}.csv'
    
    def load_examples(self):
        save_path = self.get_example_save_path()
        try:
            with open(save_path,'br') as pkl_file:
                E=pkl.load(pkl_file)
                self.Examples=E['Examples']
        except IOError as e:
            print(e)
        
    def load_all_examples_in_brain(self,label = 1):
        sections = self.get_sections_with_csv()
        examples = []
        for sectioni in sections:
            base = CellDetectorBase(self.animal,sectioni)
            base.load_examples()
            examplei = [i for tilei in base.Examples for i in tilei if i['label'] == label]
            examples += examplei
        return examples
    
    def load_features(self):
        path=self.get_feature_save_path()
        try:
            self.features = pd.read_csv(path)
        except IOError as e:
            print(e)
    
    def save_features(self):
        df=pd.DataFrame()
        i = 0
        for featurei in self.features:
            df_dict = pd.DataFrame(featurei,index = [i])
            i+=1
            df=df.append(df_dict)
        outfile=self.get_feature_save_path()
        print('df shape=',df.shape,'output_file=',outfile)
        try:
            df.to_csv(outfile,index=False)
        except IOError as e:
            print(e)
    
    def save_examples(self):
        out={'Examples':self.Examples}
        print(f'section {self.section}')
        t1=time()
        try:
            with open(self.get_example_save_path(),'wb') as pkl_file:
                pkl.dump(out,pkl_file)
        except IOError as e:
            print(e)

def get_sections_with_annotation_for_animali(animal):
    base = CellDetectorBase(animal)
    return base.get_sections_with_csv()

def get_sections_without_annotation_for_animali(animal):
    base = CellDetectorBase(animal)
    return base.get_sections_without_csv()