import os
from glob import glob

WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径

def default_data_path(code, ktype):
    path = f"{WORK_DIR}/data/{code}_{ktype}_data.csv"
    return path

def default_info_path(code):
    path = f"{WORK_DIR}/data/{code}_info.csv"
    return path

def get_codes_from_local(data_dir=DATA_DIR):
    info_files = glob(os.path.join(data_dir, "*_info.csv"))
    codes = [os.path.basename(f).split("_")[0] for f in info_files]
    
    # 写入临时文件
    with open("/tmp/localfilelist.tmp", "w") as f:
        f.write("\n".join(codes))
    
    return codes
