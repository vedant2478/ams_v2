import os
import pytz
import sqlalchemy
from time import sleep
from files.model import *
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String

TZ_INDIA = pytz.timezone("Asia/Kolkata")


if __name__ == "__main__":

    SQLALCHEMY_DATABASE_URI = "sqlite:////home/ams-core/csiams.dev.sqlite"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False}, echo=True
    )
    Session = sessionmaker()
    Session.configure(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    CURRENT_VERSION = 1.2
    NEW_VERSION = ""
    BACKUP_LOCATION = "/home/backups/"
    cabinet = session.query(AMS_Cabinet).one_or_none()
    CABINET_IP_ADDRESS = str(cabinet.ipAddress)
    exception_occured = 0

    if os.path.exists(BACKUP_LOCATION):
        os.system(f"rm -rf {BACKUP_LOCATION}")

    packages_to_install = {
        "requests": {
            "main_file": "requests-2.28.1.tar.gz",
            "sub_packages": [
                "certifi-2022.6.15.tar.gz",
                "charset-normalizer-2.1.1.tar.gz",
                "idna-3.3.tar.gz",
                "urllib3-1.26.12.tar.gz",
            ],
        },
        "schedule": {"main_file": "schedule-1.1.0.tar.gz", "sub_packages": []},
    }

    files_to_update = ["model.py", "main-csi.py", "ams-start.sh"]

    files_to_create = ["apicalls.py", "emdoor.py"]

    files_to_delete = []

    print("initializing the process .................. ")
    sleep(2)

    try:

        tables = ["eventlogs", "access_log"]
        for tbl in tables:
            try:
                query = f"PRAGMA table_info('{tbl}');"
                flag = False
                for record in list(engine.execute(query)):
                    if record[1] == "is_posted":
                        flag = True
                        break
                if flag:
                    print("column exists")
                else:
                    print("column does not exists")
                    col_add_query = f"""
                        alter table {tbl} 
                        add column is_posted integer not null default 0
                    """
                    engine.execute(col_add_query)
                    print(f"successfully created new column in table {tbl} ..")
            except Exception as e:
                exception_occured += 1
                print("exception occured while updating table structure")
                print(e)

        try:
            query = f"PRAGMA table_info('keys');"
            flag = False
            for record in list(engine.execute(query)):
                if record[1] == "keyTakenByUser":
                    flag = True
                    break
            if not flag:
                col_add_query = f"""
                    alter table keys 
                    add column keyTakenByUser varchar
                """
                engine.execute(col_add_query)
                print("column added successfully ...")
        except Exception as e:
            print(e)

        meta = MetaData()
        activity_progress_status = Table(
            "activity_progress_status",
            meta,
            Column("id", Integer, primary_key=True),
            Column("is_active", Integer),
        )
        meta.create_all(engine)
        ams_activity_progress_status = AMS_Activity_Progress_Status(is_active=0)
        session.add(ams_activity_progress_status)
        session.commit()
        print("table created successfully")

        event = (
            session.query(AMS_Event_Types)
            .filter(AMS_Event_Types.eventDescription == "Emergency Door Open")
            .one_or_none()
        )
        event.eventId = 14
        session.commit()

        backup_folder_name = f"AMS_PYTHON_LOCAL_{CURRENT_VERSION}_{datetime.now(TZ_INDIA).date()}_{datetime.now(TZ_INDIA).time()}"
        backup_final_location = os.path.join(BACKUP_LOCATION, backup_folder_name)
        if not os.path.exists(backup_final_location):
            os.makedirs(backup_final_location)
        print(backup_final_location)
        os.system(f"scp -r /home/ams-core/ {backup_final_location}/")
        print(
            "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
        )
        print(
            "\n\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@   Backup Completed Successfully   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n\n"
        )
        print(
            "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
        )

        if len(packages_to_install) > 0:
            for pkg_name, pkg_files in packages_to_install.items():
                print(pkg_name)
                main_file = packages_to_install[pkg_name]["main_file"]
                if main_file:
                    print(main_file)
                    sub_packages = packages_to_install[pkg_name]["sub_packages"]
                    if len(sub_packages) > 0:
                        print("sub packages found")
                        print(sub_packages)
                        for pkg in sub_packages:
                            print(pkg)
                            os.system(f"tar -xvzf packages/{pkg}")
                            os.system(f"tar -xvzf packages/{pkg} -C /home/")
                            os.system("touch `find . -type f`")
                            current_path = os.getcwd()
                            os.chdir(os.path.join(current_path, pkg[:-7]))
                            # os.system(f'sudo python setup.py install')
                            os.system(f"python3 setup.py install")
                            os.chdir(current_path)
                        print("will install main package here!")
                        main_package = packages_to_install[pkg_name]["main_file"]
                        os.system(f"tar -xvzf packages/{main_package}")
                        os.system(f"tar -xvzf packages/{main_package} -C /home/")
                        os.system("touch `find . -type f`")
                        current_path = os.getcwd()
                        os.chdir(os.path.join(current_path, main_package[:-7]))
                        # os.system(f'sudo python setup.py install')
                        os.system(f"python3 setup.py install")
                        os.chdir(current_path)
                    else:
                        print(sub_packages)
                        print("will install main package directly here!")
                        main_package = packages_to_install[pkg_name]["main_file"]
                        os.system(f"tar -xvzf packages/{main_package}")
                        os.system(f"tar -xvzf packages/{main_package} -C /home/")
                        os.system("touch `find . -type f`")
                        current_path = os.getcwd()
                        os.chdir(os.path.join(current_path, main_package[:-7]))
                        # os.system(f'sudo python setup.py install')
                        os.system(f"python3 setup.py install")
                        os.chdir(current_path)

        if len(files_to_create) > 0:
            for file in files_to_create:
                try:
                    os.system(f"scp ./files/{file} /home/ams-core/")
                    print(f"{file} created successfully")
                except Exception as e:
                    exception_occured += 1
                    print("exception occured while creating new files")
                    print(e)

        if len(files_to_update) > 0:
            for file in files_to_update:
                try:
                    os.system(f"scp ./files/{file} /home/ams-core/")
                    print(f"{file} updated successfully")
                    if file == "ams-start.sh":
                        os.system(
                            f"scp /home/ams-core/ams-start.sh /lib/systemd/system/"
                        )
                except Exception as e:
                    exception_occured += 1
                    print("exception occured while updating files")
                    print(e)

        os.system("chmod 777 /home/ams-core/ams-start.sh")

        print(
            "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
        )
        print(
            "\n\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@   Firmware Updated Successfully   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n\n"
        )
        print(
            "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
        )

        if exception_occured > 0:
            print(
                f"total {exception_occured} exception/s occured !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )
            os.system(f"scp -r {backup_final_location}/ams-core/ /home/")
            raise Exception("exception occured during update")

    except Exception as e:
        raise RuntimeError()
