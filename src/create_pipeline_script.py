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
import sys, os, socket
from timeit import default_timer as timer
from datetime import datetime
from lib.logger import get_logger
import tests.checklist as check # 'PRE-FLIGHT CHECKLIST'
from lib.pipeline import Pipeline


def run_pipeline(animal, channel, downsample, step, progress_log):

    pipeline = Pipeline(animal, channel, downsample)

    # START LOG OUTPUT
    category = "PIPELINE: check programs"
    now = datetime.now()
    dt_start = now.strftime("%Y-%m-%d %H:%M:%S")
    status = 'start'
    out = "\n" + str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status) + "\n"

    start = timer()
    pipeline.check_programs()
    end = timer()

    status = f'end - {end - start} s'
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status) + "\n"
    print(cur_out)
    out += cur_out
    with open(progress_log, 'a') as fh:
        fh.write(out)

    category = "PIPELINE: create meta"
    now = datetime.now()
    dt_start = now.strftime("%Y-%m-%d %H:%M:%S")
    status = 'start'
    out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status) + "\n"

    start = timer()
    pipeline.create_meta()
    end = timer()

    now = datetime.now()
    dt_start = now.strftime("%Y-%m-%d %H:%M:%S")
    status = f'end - {end - start} s'
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status) + "\n"
    print(cur_out)
    out += cur_out
    with open(progress_log, 'a') as fh:
        fh.write(out)

    exit()

    start = timer()
    pipeline.create_tifs()
    end = timer()
    print(f'Create tifs took {end - start} seconds')    
    if step > 0:
        start = timer()
        pipeline.create_preps()
        pipeline.create_normalized()
        pipeline.create_masks()
        end = timer()
        print(f'Creating normalized and masks took {end - start} seconds')    
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
    if step > 2:
        start = timer()
        pipeline.create_elastix()
        pipeline.create_aligned()
        end = timer()
        print(f'Creating elastix and alignment took {end - start} seconds')    
    if step > 3:
        start = timer()
        pipeline.create_neuroglancer_image()
        pipeline.create_downsampling()
        end = timer()
        print(f'Last step: creating neuroglancer images took {end - start} seconds')    


def main():
    now = datetime.now()
    dt_start = now.strftime("%Y-%m-%d %H:%M:%S")
    category = "START SCRIPT"
    out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" # DUMP TO LOG ONCE PATH IS CHECKED
    print(out)

    base_working_dir = os.getcwd()
    sys.path.append(base_working_dir)  # APPEND CURRENT WORKING DIRECTORY TO PYTHONPATH

    # CHECK FOR PREREQUISITES PRIOR TO PROCESSING
    status = check.check_env()
    category = "CHECKLIST: env variables"
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status)
    print(cur_out)
    out += "\n" + cur_out

    status = check.check_files(base_working_dir)
    category = "CHECKLIST: core files"
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status)
    print(cur_out)
    out += "\n" + cur_out

    status = check.check_imports()
    category = "CHECKLIST: imports"
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status)
    print(cur_out)
    out += "\n" + cur_out

    status = check.check_db(base_working_dir)
    category = "CHECKLIST: database"
    cur_out = str(dt_start) + " " + str(socket.gethostname()) + " : " + "[" + category + "]" + " " + str(status)
    print(cur_out)
    out += "\n" + cur_out

    # TRY TO SPLIT INTO RAW IMAGE PARSING VS. NEUROGLANCER (22-DEC-2021 EDIT PROPOSAL) [LOW PRIORITY]
    #from lib.pipeline import Pipeline

    # Note: 'prep_id' in database
    animal = 'test'

    channel = 1
    downsample = True
    step = 4 # MEANING : COMPLETE ALL STEPS


    # ADD LOGGING TO FILE - IN OUTPUT_PATH AND FOR BIOSOURCE TO BE PROCESSED
    OUTPUT_PATH = os.environ.get('OUTPUT_PATH')
    progress_log = os.path.join(OUTPUT_PATH, animal, 'preprocessing-pipeline.log')
    os.makedirs(os.path.join(OUTPUT_PATH, animal), exist_ok=True)
    with open(progress_log, 'w+') as fh:
        fh.write(out)

    run_pipeline(animal, 1, downsample, step, progress_log)

    # run_pipeline(animal, channel = 2, downsample = downsample, step = step)
    # run_pipeline(animal, 3, downsample,step)
    #downsample = False
    #run_pipeline(animal, 1, downsample, step)

    # run_pipeline(animal, 2, downsample,step)
    # run_pipeline(animal, 3, downsample,step)


if __name__ == '__main__':
    main()