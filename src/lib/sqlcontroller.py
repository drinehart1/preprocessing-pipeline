"""
This is the base sql class. It is mostly used per animal, so the init function
needs an animal passed to the constructor
It also needs for the animal, histology and scan run tables to be
filled out for each animal to use
"""
import sys



from lib.sql_setup import session, pooledsession
from model.file_log import FileLog
from model.urlModel import UrlModel
from model.task import Task, ProgressLookup
from model.layer_data import LayerData
from model.structure import Structure
from model.slide_czi_to_tif import SlideCziTif
from model.slide import Slide
from model.section import Section
from model.scan_run import ScanRun
from model.histology import Histology
from model.animal import Animal
from model.elastix_transformation import ElastixTransformation
import json
import pandas as pd
from collections import OrderedDict
from datetime import datetime
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound


class SqlController(object):
    """ Create a class for processing the pipeline,
    """

    def __init__(self, animal):
        """ setup the attributes for the SlidesProcessor class
            Args:
                animal: object of animal to process
        """
        self.session = session
        try:
            self.animal = self.session.query(Animal).filter(
                Animal.prep_id == animal).one()
        except NoResultFound:
            print(f'No animal/brain with the name {animal} was found in the database.')
            sys.exit()
        try:
            self.histology = self.session.query(Histology).filter(
                Histology.prep_id == animal).one()
        except NoResultFound:
            print(f'No histology for {animal}')
        try:
            self.scan_run = self.session.query(ScanRun).filter(
                ScanRun.prep_id == animal).order_by(ScanRun.id.desc()).one()
        except NoResultFound:
            print(f'No scan run for {animal}')
        self.slides = None
        self.tifs = None
        self.valid_sections = OrderedDict()
        # fill up the metadata_cache variable
        # self.session.close()
    
    def animal_exists(self,animal):
        return bool(self.session.query(Animal).filter(Animal.prep_id == animal).first())

    def get_animal_list(self):
        results = self.session.query(Animal).all()
        animals = []
        for resulti in results:
            animals.append(resulti.prep_id)
        return animals
    
    def get_annotated_animals(self):
        results = self.session.query(LayerData)\
            .filter(LayerData.active.is_(True))\
            .filter(LayerData.input_type_id == 1)\
            .filter(LayerData.person_id == 2)\
            .filter(LayerData.layer == 'COM').all()
        return np.unique([ri.prep_id for ri in results])

    def get_values_from_column(self, query_result):
        query_result = query_result.all()
        query_result = [entryi[0] for entryi in query_result]
        return query_result

    def get_section(self, ID):
        """
        The sections table is a view and it is already filtered by active and file_status = 'good'
        This qeury returns a single section by id.
        Args:
            id: integer primary key

        Returns: one section
        """
        return self.session.query(Section).filter(Section.id == ID).one()

    def get_slide(self, ID):
        """
        Args:
            id: integer primary key

        Returns: one slide
        """
        return self.session.query(Slide).filter(Slide.id == ID).one()

    def get_tif(self, ID):
        """
        Args:
            id: integer primary key

        Returns: one tif
        """
        return self.session.query(SlideCziTif).filter(SlideCziTif.id == ID).one()

    def get_urlModel(self, ID):
        """
        Args:
            id: integer primary key

        Returns: one neuroglancer json object
        """
        return self.session.query(UrlModel).filter(UrlModel.id == ID).one()

    def get_url_id_list(self):
        urls = self.session.query(UrlModel).all()
        ids = [url.id for url in urls]
        return ids

    def get_sections(self, animal, channel):
        """
        The sections table is a view and it is already filtered by active and file_status = 'good'
        The ordering is important. This needs to come from the histology table.
        Args:
            animal: the animal to query
            channel: 1 or 2 or 3.

        Returns: list of sections in order

        """
        orderby = self.histology.side_sectioned_first

        if orderby == 'DESC':
            sections = self.session.query(Section).filter(Section.prep_id == animal)\
                .filter(Section.channel == channel)\
                .order_by(Section.slide_physical_id.desc())\
                .order_by(Section.scene_number.desc()).all()
        else:
            sections = self.session.query(Section).filter(Section.prep_id == animal)\
                .filter(Section.channel == channel)\
                .order_by(Section.slide_physical_id.asc())\
                .order_by(Section.scene_number.asc()).all()

        return sections

    def get_distinct_section_filenames(self, animal, channel):
        """
        Very similar to the get_sections query but this will return a list of
        distinct file names. Since some of the scenes get duplicated in the QA process,
        we need to get the tifs without duplicates. The duplicates will then get replicated
        with the get_sections method. The order doesn't matter here.
        Args:
            animal: the animal to query
            channel: 1 or 2 or 3.

        Returns: list of sections with distinct file names

        """
        sections = self.session.query(Section.czi_file, Section.file_name, Section.scene_index,  Section.channel_index).distinct()\
            .filter(Section.prep_id == animal).filter(
            Section.channel == channel).all()

        return sections

    def get_slide_czi_to_tifs(self, channel):
        slides = self.session.query(Slide).filter(Slide.scan_run_id == self.scan_run.id)\
            .filter(Slide.slide_status == 'Good').all()
        slide_czi_to_tifs = self.session.query(SlideCziTif).filter(SlideCziTif.channel == channel)\
            .filter(SlideCziTif.slide_id.in_([slide.id for slide in slides]))\
            .filter(SlideCziTif.active == 1).all()

        return slide_czi_to_tifs

    def update_row(self, row):
        try:
            self.session.merge(row)
            self.session.commit()
        except Exception as e:
            print(f'No merge for  {e}')
            self.session.rollback()

    def update_scanrun(self, id):
        width = self.session.query(func.max(SlideCziTif.width)).join(Slide).join(ScanRun)\
            .filter(SlideCziTif.active == True) \
            .filter(ScanRun.id == id).scalar()
        height = self.session.query(func.max(SlideCziTif.height)).join(Slide).join(ScanRun)\
            .filter(SlideCziTif.active == True) \
            .filter(ScanRun.id == id).scalar()
        SAFEMAX = 10000
        LITTLE_BIT_MORE = 500
        # just to be safe, we don't want to update numbers that aren't realistic
        if height > SAFEMAX and width > SAFEMAX:
            height = round(height, -3)
            width = round(width, -3)
            height += LITTLE_BIT_MORE
            width += LITTLE_BIT_MORE
            # width and height get flipped
            try:
                self.session.query(ScanRun).filter(ScanRun.id == id).update(
                    {'width': height, 'height': width})
                self.session.commit()
            except Exception as e:
                print(f'No merge for  {e}')
                self.session.rollback()

    def update_tif(self, id, width, height):
        try:
            self.session.query(SlideCziTif).filter(
                SlideCziTif.id == id).update({'width': width, 'height': height})
            self.session.commit()
        except Exception as e:
            print(f'No merge for  {e}')
            self.session.rollback()

    def get_sections_numbers(self, animal):
        sections = self.session.query(Section).filter(
            Section.prep_id == animal).filter(Section.channel == 1).all()

        section_numbers = []
        for i, r in enumerate(sections):
            section_numbers.append(i)

        return section_numbers

    def get_sections_dict(self, animal):
        sections = self.session.query(Section).filter(
            Section.prep_id == animal).filter(Section.channel == 1).all()

        sections_dict = {}
        for i, r in enumerate(sections):
            sections_dict[i] = str(i).zfill(3) + 'tif'

        return sections_dict

    def get_structure(self, abbrv):
        """
        Returns a structure
        This search has to be case sensitive!
        :param abbrv: the abbreviation of the structure
        :return: structure object
        """
        return self.session.query(Structure).filter(Structure.abbreviation == func.binary(abbrv)).one()
    
    def get_layer_data(self,search_dictionary):
        query_start = self.session.query(LayerData)
        for key, value in search_dictionary.items():
            query_start = eval(f'query_start.filter(LayerData.{key}=="{value}")')
        return query_start.all()

    def get_coordinates_from_query_result(self,query_result):
        coord = []
        resolution = self.scan_run.resolution
        for resulti in query_result:
            coord.append([resulti.x/resolution,resulti.y/resolution,int(resulti.section/20)])
        return(np.array(coord))

    def get_structure_color(self, abbrv):
        """
        Returns a color code as int
        This search has to be case sensitive!
        :param abbrv: the abbreviation of the structure
        :return: tuple of rgb
        """
        row = self.session.query(Structure).filter(
            Structure.abbreviation == func.binary(abbrv)).one()
        return int(row.color)

    def get_structure_color_rgb(self, abbrv):
        """
        Returns a color code in RGB format like (1,2,3)
        This search has to be case sensitive!
        :param abbrv: the abbreviation of the structure
        :return: tuple of rgb
        """
        row = self.session.query(Structure).filter(
            Structure.abbreviation == func.binary(abbrv)).one()
        hexa = row.hexadecimal
        h = hexa.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def get_structures(self):
        return self.session.query(Structure).filter(Structure.active.is_(True)).all()

    def get_structures_dict(self):
        rows = self.session.query(Structure)\
            .filter(Structure.abbreviation != 'R')\
            .filter(Structure.is_structure ==1).filter(
            Structure.active.is_(True)).all()
        structures_dict = {}
        for structure in rows:
            structures_dict[structure.abbreviation] = [
                structure.description, structure.color]

        return structures_dict

    def get_structures_list(self):
        rows = self.session.query(Structure).filter(Structure.id<52)\
                .filter(Structure.abbreviation != 'R').filter(Structure.active.is_(
            True)).order_by(Structure.abbreviation.asc()).all()
        structures = []
        for structure in rows:
            structures.append(structure.abbreviation)

        return structures

    def get_sided_structures(self):
        """
        Not sure when/if this is needed, but will only return sided structures
        :return: list of structures that are not singules
        """
        rows = self.session.query(Structure).filter(
            Structure.active.is_(True)).all()
        structures = []
        for structure in rows:
            if "_" in structure.abbreviation:
                structures.append(structure.abbreviation)

        return sorted(structures)

    def get_section_count(self, animal):
        try:
            count = self.session.query(Section).filter(
                Section.prep_id == animal).filter(Section.channel == 1).count()
        except:
            count = 666
        return count

    def get_current_task(self, animal):
        step = None
        try:
            lookup_id = self.session.query(func.max(Task.lookup_id)).filter(Task.prep_id == animal) \
                .filter(Task.completed.is_(True)).scalar()
        except NoResultFound as nrf:
            print('No results for {} error: {}'.format(animal, nrf))
            return step

        try:
            lookup = self.session.query(ProgressLookup).filter(
                ProgressLookup.id == lookup_id).one()
        except NoResultFound as nrf:
            print('Bad lookup code for {} error: {}'.format(lookup_id, nrf))
            return step

        return lookup.description

    def set_task(self, animal, lookup_id):
        """
        Look up the lookup up from the step. Check if the animal already exists,
        if not, insert, otherwise, update
        Args:
            animal: string of the animal you are working on
            lookup_id: current lookup ID
        Returns:
            nothing, just merges
        """
        try:
            lookup = self.session.query(ProgressLookup) \
                .filter(ProgressLookup.id == lookup_id) \
                .limit(1).one()
        except NoResultFound:
            print('No lookup for {} so we will enter one.'.format(lookup_id))
        try:
            task = self.session.query(Task).filter(Task.lookup_id == lookup.id) \
                .filter(Task.prep_id == animal).one()
        except NoResultFound:
            print('No step for {}, so creating new task.'.format(lookup_id))
            task = Task(animal, lookup.id, True)

        try:
            self.session.merge(task)
            self.session.commit()
        except:
            print('Bad lookup code for {}'.format(lookup.id))
            self.session.rollback()
    
    def structure_abbreviation_to_id(self,abbreviation):
        try:
            structure = self.get_structure(str(abbreviation).strip())
        except NoResultFound as nrf:
            print(f'No structure found for {abbreviation} {nrf}')
            return
        return structure.id

    def add_layer_data(self, abbreviation, animal, layer, x, y, section, 
                       person_id, input_type_id):
        """
        Look up the structure id from the structure.
        Args:
            structure: abbreviation with the _L or _R ending
            animal: prep_id
            x=float of x coordinate
            y=float of y coordinate
            section = int of z/section coordinate
        Returns:
            nothing, just merges
        try:
            structure = self.session.query(Structure) \
                .filter(Structure.abbreviation == func.binary(abbreviation)).one()
        except NoResultFound:
            print(f'No structure for {abbreviation}')
        """

        structure_id = self.structure_abbreviation_to_id(abbreviation)
        coordinates = (x,y,section)
        self.add_layer_data_row(animal,person_id,input_type_id,coordinates,structure_id,layer)

    def get_com_dict(self, prep_id, input_type_id=1, person_id=2,active = True):
        return self.get_layer_data_entry( prep_id = prep_id, input_type_id=input_type_id,\
             person_id=person_id,active = active,layer = 'COM')
    
    def get_layer_data_entry(self, prep_id, input_type_id=1, person_id=2,active = True,layer = 'COM'):
        rows = self.session.query(LayerData)\
            .filter(LayerData.active.is_(active))\
            .filter(LayerData.prep_id == prep_id)\
            .filter(LayerData.input_type_id == input_type_id)\
            .filter(LayerData.person_id == person_id)\
            .filter(LayerData.layer == layer)\
            .all()
        row_dict = {}
        for row in rows:
            structure = row.structure.abbreviation
            row_dict[structure] = [row.x, row.y, row.section]
        return row_dict

    def get_atlas_centers(self):
        PERSON_ID_LAUREN = 16
        INPUT_TYPE_MANUAL = 1
        return self.get_com_dict('Atlas',INPUT_TYPE_MANUAL,PERSON_ID_LAUREN)

    def get_point_dataframe(self, id):
        """
        :param id: primary key from the url. Look at:
         https://activebrainatlas.ucsd.edu/activebrainatlas/admin/neuroglancer/points/164/change/
         for example use 164 for the primary key
         to get the ID
        :return: a pandas dataframe
        """

        try:
            urlModel = self.session.query(
                UrlModel).filter(UrlModel.id == id).one()
        except NoResultFound as nrf:
            print('Bad ID for {} error: {}'.format(id, nrf))
            return

        result = None
        dfs = []
        if urlModel.url is not None:
            json_txt = json.loads(urlModel.url)
            layers = json_txt['layers']
            for l in layers:
                if 'annotations' in l:
                    name = l['name']
                    annotation = l['annotations']
                    d = [row['point'] for row in annotation]
                    df = pd.DataFrame(d, columns=['X', 'Y', 'Section'])
                    df['X'] = df['X'].astype(int)
                    df['Y'] = df['Y'].astype(int)
                    df['Section'] = df['Section'].astype(int)
                    df['Layer'] = name
                    df = df[['Layer', 'X', 'Y', 'Section']]
                    dfs.append(df)
            if len(dfs) == 0:
                result = None
            elif len(dfs) == 1:
                result = dfs[0]
            else:
                result = pd.concat(dfs)

        return result

    def get_progress_id(self, downsample, channel, action):

        try:
            lookup = self.session.query(ProgressLookup) \
                .filter(ProgressLookup.downsample == downsample) \
                .filter(ProgressLookup.channel == channel) \
                .filter(ProgressLookup.action == action).one()
        except NoResultFound as nrf:
            print(
                f'Bad lookup code for {downsample} {channel} {action} error: {nrf}')
            return 0

        return lookup.id

    def check_elastix_row(self, animal, section):
        row_exists = bool(self.session.query(ElastixTransformation).filter(
            ElastixTransformation.prep_id == animal,
            ElastixTransformation.section == section).first())
        return row_exists

    def add_row(self,data):
        try:
            self.session.add(data)
            self.session.commit()
        except Exception as e:
            print(f'No merge {e}')
            self.session.rollback()
        finally:
            self.session.close()
        
    def add_url(self,content,title,person_id):
        url = UrlModel(url = content,comments = title,person_id = person_id)
        self.add_row(url)

    def delete_url(self,title,person_id):
        self.session.query(UrlModel)\
            .filter(UrlModel.comments == title)\
            .filter(UrlModel.person_id == person_id).delete()
        self.session.commit()

    def add_elastix_row(self, animal, section, rotation, xshift, yshift):
        data = ElastixTransformation(
            prep_id=animal, section=section, rotation=rotation, xshift=xshift, yshift=yshift,
            created=datetime.utcnow(), active=True)
        self.add_row(data)

    def add_layer_data_row(self,animal,person_id,input_type_id,coordinates,structure_id,layer):
        x,y,z = coordinates
        data = LayerData(prep_id = animal, person_id = person_id, input_type_id = input_type_id, x=x, y=y, \
            section=z,structure_id=structure_id,layer=layer)
        self.add_row(data)
    
    def add_com(self, prep_id, abbreviation, coordinates, person_id=2 , input_type_id = 1):
        structure_id = self.structure_abbreviation_to_id(abbreviation)
        if self.layer_data_row_exists(animal=prep_id,person_id = person_id,input_type_id = input_type_id,\
            structure_id = structure_id,layer = 'COM'):
            self.delete_layer_data_row(animal=prep_id,person_id = person_id,input_type_id = input_type_id,\
                structure_id = structure_id,layer = 'COM')
        self.add_layer_data_row(animal = prep_id,person_id = person_id,input_type_id = input_type_id,\
            coordinates = coordinates,structure_id = structure_id,layer = 'COM')
    
    def url_exists(self,comments):
        row_exists = bool(self.session.query(UrlModel).filter(UrlModel.comments == comments).first())
        return row_exists

    def layer_data_row_exists(self,animal, person_id, input_type_id, structure_id, layer):
        row_exists = bool(self.session.query(LayerData).filter(
            LayerData.prep_id == animal, 
            LayerData.person_id == person_id, 
            LayerData.input_type_id == input_type_id, 
            LayerData.structure_id == structure_id,
            LayerData.layer == layer).first())
        return row_exists
 
    def delete_layer_data_row(self,animal,person_id,input_type_id,structure_id,layer):
        self.session.query(LayerData)\
            .filter(LayerData.active.is_(True))\
            .filter(LayerData.prep_id == animal)\
            .filter(LayerData.input_type_id == input_type_id)\
            .filter(LayerData.person_id == person_id)\
            .filter(LayerData.structure_id == structure_id)\
            .filter(LayerData.layer == layer).delete()
        self.session.commit()

    def clear_elastix(self, animal):
        self.session.query(ElastixTransformation).filter(ElastixTransformation.prep_id == animal)\
            .delete()

    def convert_coordinate_pixel_to_microns(self,coordinates):
        resolution = self.scan_run.resolution
        self.session.close()
        x,y,z = coordinates
        x*=resolution
        y*=resolution
        z*=20
        return x,y,z

def file_processed(animal, progress_id, filename):
    """
    Args:
        animal: prep_id
        progress_id: ID from progress_lookup table
        filename: filename you are working on
    Returns:
        boolean if file exists or not
    """
    try:
        file_log = pooledsession.query(FileLog) \
            .filter(FileLog.prep_id == animal) \
            .filter(FileLog.progress_id == progress_id) \
            .filter(FileLog.filename == filename).one()
    except NoResultFound as nrf:
        return False
    finally:
        pooledsession.close()

    return True

def set_file_completed(animal, progress_id, filename):
    """
    Args:
        animal: prep_id
        progress_id: ID from progress_lookup table
        filename: filename you are working on
    Returns:
        nothing, just merges
    """

    file_log = FileLog(prep_id=animal, progress_id=progress_id, filename=filename,
                       created=datetime.utcnow(), active=True)

    try:
        pooledsession.add(file_log)
        pooledsession.commit()
    except Exception as e:
        print(f'No merge for {animal} {filename} {e}')
        pooledsession.rollback()
    finally:
        pooledsession.close()


    

