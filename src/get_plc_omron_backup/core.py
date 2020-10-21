#!/usr/bin/python3

import ftplib
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import simplejson as json

from aion.microservice import main_decorator, Options
from aion.kanban import Kanban

from aion.mysql import BaseMysqlAccess
from aion.logger import lprint,lprint_exception

SERVICE_NAME = "get-plc-backup-omron-with-ftp"
CONFIG_PATH = 'config'
FTP_TIMEOUT = 10

class RobotBackupDB(BaseMysqlAccess):
    def __init__(self):
        super().__init__("Maintenance")

    def set_backup_to_db(self, backup_save_path, backup_date, backup_state):
        query = f"""
                insert into backupfiles(path, date, state)
                values ('{backup_save_path}', '{backup_date}', {backup_state})
                """
        ret = self.set_query(query)
        if not ret:
            lprint_exception('failed to insert new backup data')
        else:
            self.commit_query()


class FtpClient():
    ftp = None

    def __init__(self, host, user, passwd):
        if user and passwd:
            # login with ftp user
            lprint(f"connect to ftp server: {host}:{user}")
            self.ftp = ftplib.FTP(host, user, passwd, timeout=FTP_TIMEOUT)
        else:
            # login with anonymous
            lprint(f"connect to ftp server: {host}")
            self.ftp = ftplib.FTP(host=host, timeout=FTP_TIMEOUT)
        self.ftp.cwd('MEMCARD1')

    def get(self, backup_file, backup_save_path):
        self.ftp.retrlines('LIST')
        lprint(f"downloading... {backup_file}")
        self.ftp.retrbinary(f'RETR {backup_file}', 
            open(backup_save_path, 'wb').write)

    def __del__(self):
        if self.ftp:
            self.ftp.quit()
            lprint(f"disconnect to ftp server")


@main_decorator(SERVICE_NAME)
def main(opt: Options):
    # get cache kanban
    conn = opt.get_conn()
    num = opt.get_number()
    #kanban = conn.get_one_kanban(SERVICE_NAME, num)
    kanban: Kanban = conn.set_kanban(SERVICE_NAME, num)

    data_path = f"/var/lib/aion/Data/{SERVICE_NAME}_{num}/data"

    # open config file
    config = None
    with open(os.path.join(CONFIG_PATH, "config.json")) as f:
        config = json.load(f)

    result_status = True

    JST = timezone(timedelta(hours=+9), 'JST')
    backup_time = datetime.now(JST)
    backup_dir = os.path.join(
        data_path,
        backup_time.strftime('%Y%m%d%H%M%S')
    )
    backup_file = config.get('ftp-backup-file')
    backup_save_path = {}
    for bf in backup_file:
        backup_save_path[bf] = os.path.join(backup_dir, bf)

    host = config.get('ftp-server')
    user = config.get('ftp-user')
    passwd = config.get('ftp-passwd')

    # make backup directory
    for bsp in backup_save_path.values():
        dirname = os.path.dirname(bsp)
        lprint(f"make backup directory: {dirname}")
        os.makedirs(dirname, exist_ok=True)
        ### don't mkdir backup_dir becaus dirs are defined in backup_file ###

    try:
        ftpc = FtpClient(host, user, passwd)
        for bf,bsp in backup_save_path.items():
            ftpc.get(bf, bsp)
    except ftplib.all_errors as error:
        lprint_exception(f"ftp connection failed : {error}")
        result_status = False

    # write backup history to db
    try:
        with RobotBackupDB() as db:
            backup_state = 1 if result_status else 2 # 1:succeeded 2:failed
            for bsp in backup_save_path.values():
                db.set_backup_to_db(
                    bsp, 
                    backup_time.strftime('%Y-%m-%d %H:%M:%S'), 
                    backup_state)
    finally:
        # output after kanban
        conn.output_kanban(
            result=True,
            connection_key="key",
            output_data_path=data_path,
            process_number=num,
        )
    return



if __name__ == "__main__":
    main()

