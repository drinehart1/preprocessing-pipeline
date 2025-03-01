"""
This program will create everything.
The only required argument is the animal. By default it will work on channel=1
and downsample = True. Run them in this sequence:
    python src/create_pipeline.py --animal DKXX
    python src/create_pipeline.py --animal DKXX --channel 2
    python src/create_pipeline.py --animal DKXX --channel 3
    python src/create_pipeline.py --animal DKXX --channel 1 --downsample false
    python src/create_pipeline.py --animal DKXX --channel 2 --downsample false
    python src/create_pipeline.py --animal DKXX --channel 3 --downsample false

Human intervention is required at several points in the process:
1. After create meta - the user needs to check the database and verify the images 
are in the correct order and the images look good.
1. After the first create mask method - the user needs to check the colored masks
and possible dilate or crop them.
1. After the alignment process - the user needs to verify the alignment looks good. 
increasing the step size will make the pipeline move forward in the process.
see: src/python/create_pipeline.py -h
for more information.
"""
import argparse
from timeit import default_timer as timer
from lib.pipeline import Pipeline
from lib.logger import get_logger

if __name__ == '__main__':
    
    steps = """
    start=0, prep, normalized and masks=1, mask, clean and histograms=2, 
     elastix and alignment=3, neuroglancer=4
     """
    parser = argparse.ArgumentParser(description='Work on Animal')
    parser.add_argument('--animal', help='Enter the animal', required=True)
    parser.add_argument('--channel', help='Enter channel', required=False, default=1)
    parser.add_argument('--downsample', help='Enter true or false', required=False, default='true')
    parser.add_argument('--step', help=steps, required=False, default=0)
    

    args = parser.parse_args()
    animal = args.animal
    channel = int(args.channel)
    downsample = bool({'true': True, 'false': False}[str(args.downsample).lower()])
    step = int(args.step)
    logger = get_logger(animal)

    pipeline = Pipeline(animal, channel, downsample)
    start = timer()
    # pipeline.debug = True
    pipeline.check_programs()
    end = timer()
    print(f'Check programs took {end - start} seconds')    
    # logger.info(f'Check programs took {end - start} seconds')
    start = timer()
    pipeline.create_meta()
    end = timer()
    print(f'Create meta took {end - start} seconds')    
    # logger.info(f'Ceate meta took {end - start} seconds')
    start = timer()
    pipeline.create_tifs()
    end = timer()
    print(f'Create tifs took {end - start} seconds')    
    # logger.info(f'Create tifs took {end - start} seconds')
    if step > 0:
        start = timer()
        pipeline.create_preps()
        pipeline.create_normalized()
        pipeline.create_masks()
        end = timer()
        print(f'Creating normalized and masks took {end - start} seconds')    
        # logger.info(f'Create preps, normalized and masks took {end - start} seconds')
    if step > 1:
        start = timer()
        pipeline.create_masks_final()
        print('\tFinished create_masks final')    
        pipeline.create_clean()
        print('\tFinished clean')    
        pipeline.create_histograms(single=True)
        print('\tFinished histogram single')    
        pipeline.create_histograms(single=False)
        print('\tFinished histograms combined')    
        end = timer()
        print(f'Creating masks, cleaning and histograms took {end - start} seconds')    
        # logger.info(f'Creating masks, cleaning and histograms took {end - start} seconds')
    if step > 2:
        start = timer()
        pipeline.create_elastix()
        pipeline.create_aligned()
        end = timer()
        print(f'Creating elastix and alignment took {end - start} seconds')    
        # logger.info(f'Create elastix and alignment took {end - start} seconds')
    if step > 3:
        start = timer()
        pipeline.create_neuroglancer_image()
        pipeline.create_downsampling()
        end = timer()
        print(f'Last step: creating neuroglancer images took {end - start} seconds')    

    
