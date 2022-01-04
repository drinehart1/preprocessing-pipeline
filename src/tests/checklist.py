'''
    TO BE CALLED PRIOR TO ANY PROCESSING
    CHECKS FOR ANY [CRITICAL] MISSING PREREQUISITES
'''
import sys
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv # LOAD ENVIRONNMENT VARIABLES FROM .env FILE

def check_env():
    ''' IF PYTHONPATH ENVIRONMENT VARIABLES ARE NOT ALREADY SET, SET FROM .env
        REQUIRED: PYTHONPATH, BFTOOLS_PATH, MAGICK_TMPDIR, BF_MAX_MEM
    '''

    load_dotenv()  # LOADS ENVIRONMENT VARIABLES FROM .env FILE
    envdict = {}
    status = False

    envdict['PYTHONPATH'] = os.getenv("PYTHONPATH")
    envdict['BFTOOLS_PATH'] = os.environ.get('BFTOOLS_PATH')
    envdict['MAGICK_TMPDIR'] = os.environ.get('MAGICK_TMPDIR')
    envdict['BF_MAX_MEM'] = os.environ.get('BF_MAX_MEM')
    envdict['_JAVA_OPTIONS'] = os.environ.get('_JAVA_OPTIONS')
    envdict['CV_IO_MAX_IMAGE_PIXELS'] = os.environ.get('CV_IO_MAX_IMAGE_PIXELS')
    envdict['DB_CREDENTIALS_FILE'] = os.environ.get('DB_CREDENTIALS_FILE')
    envdict['OUTPUT_PATH'] = os.environ.get('OUTPUT_PATH')
    envdict['DATA_PATH'] = os.environ.get('DATA_PATH')

    for key, value in envdict.items():
        if value is not None:
            status = True
        else:
            raise("REQUIRED ENVIRONMENT VARIABLE NOT SET:", key)

    return status


def check_files(base_working_dir):
    ''' DETERMINE IF CORE CONFIGURATION FILES EXIST IN EXPECTED PATH LOCATIONS '''

    dctFiles = {}
    dctFiles['db_config_file'] = os.environ.get('DB_CREDENTIALS_FILE')

    status = True
    for key, value in dctFiles.items():
        filename = os.path.join(base_working_dir, '..', value) # DB_CREDENTIALS_FILE IS OUTSIDE src DIR (AND git)
        assert os.path.isfile(filename) == True, f'CONFIG FILE NOT FOUND: {filename}' # status IS MOOT IF ASSERTION FAILS; NO UPDATE

    # CHECK OUTPUT_PATH (EXISTS AND IS WRITABLE)
    OUTPUT_PATH = os.environ.get('OUTPUT_PATH')
    check_dir = os.path.isdir(OUTPUT_PATH)
    if not check_dir:
        os.makedirs(OUTPUT_PATH)

    # PATH SHOULD NOW EXIST; TEST IF WRITABLE
    writetest = os.path.join(OUTPUT_PATH, 'writetest.tmp')
    try:
        Path(writetest).touch()
    except:
        raise ("OUTPUT_PATH IS NOT WRITEABLE:", OUTPUT_PATH)
        status = False

    return status


def check_imports():
    ''' DETERMINE IF KEY IMPORTS ARE NOT AVAILABLE IN VIRTUAL ENVIRONMENT '''

    status = True
    try:
        import abakit
    except ImportError:
        raise("MODULE IMPORT ERROR: abakit")
        status = False
    return status


def check_db(base_working_dir):
    '''
        DETERMINE IF POSSIBLE TO CONNECT TO DB AND IF KEY TABLES/VIEWS ARE PRESENT
        RDBMS CREDENTIALS ARE IN ../../parameters.yaml
    '''

    db_config_file = os.getenv('DB_CREDENTIALS_FILE')
    filename = os.path.join(base_working_dir, '..', db_config_file)  # DB_CREDENTIALS_FILE IS OUTSIDE src DIR (AND git)
    status = True

    try:
        with open(filename, 'r') as stream:
            parameters = yaml.safe_load(stream)

            # CONNECT TO RDBMS
            from lib.sql_setup import session, pooledsession, engine #REVISE; REDUNDANT READ YAML FILE

            view_name = "sections"
            assert engine.dialect.has_table(engine, view_name) == True, f'DB ERROR - MISSING VIEW: {view_name}' # status IS MOOT IF ASSERTION FAILS; NO UPDATE


    except FileNotFoundError:
        raise('CONFIG FILE NOT FOUND: ' + str(filename))
        status = False

    return status


def main():
    pass


if __name__ == '__main__':
    main()