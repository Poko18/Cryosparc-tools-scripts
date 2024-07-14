import argparse
import glob
import os
import subprocess

from cryosparc.tools import CryoSPARC
from dotenv import dotenv_values

# Parse command line arguments
parser = argparse.ArgumentParser(description="Convert particles from cryoSPARC to RELION STAR format.")
parser.add_argument("project", type=str, help="cryoSPARC project name")
parser.add_argument("select2D_job_id", type=str, help="ID of the Select 2D job")
parser.add_argument("relion_project_path", type=str, help="Path to the RELION project")
parser.add_argument(
    "--pyem_path",
    type=str,
    default="/media/longstorage/Tadej/Cryosparc-tools-scripts/pyem/",
    help="Path to pyem directory",
)
parser.add_argument(
    "--star_file_output_prefix",
    type=str,
    default="particles_from_cs",
    help="Output prefix for the STAR file",
)
parser.add_argument("--baseport", type=str, default=39000, help="Cryosparc baseport (default: 39000)")
args = parser.parse_args()


# TO DO
# parse .star file and prepare mrcs links
def get_star_path(star_file_path):
    with open(star_file_path, "r") as star_file:
        for line in star_file:
            if line.startswith("000001@"):
                star_mrc_path = "/".join(line.split(" ")[0].split("000001@")[1].split("/")[:-1])

    return star_mrc_path


# Load login credentials from .env file
env_vars = dotenv_values(".env")
license = env_vars["CRYOSPARC_LICENSE_ID"]
host = env_vars["CRYOSPARC_HOST"]
email = env_vars["CRYOSPARC_EMAIL"]
password = env_vars["CRYOSPARC_PASSWORD"]

# Connect to CryoSPARC instance
cs = CryoSPARC(license=license, host=host, base_port=args.baseport, email=email, password=password)

# Retrieve arguments
project = args.project
select2d_job_id = args.select2D_job_id
relion_project_path = args.relion_project_path
pyem_path = args.pyem_path
star_file_output_prefix = args.star_file_output_prefix

# make dir if it doesnt exist
os.makedirs(relion_project_path, exist_ok=True)

# Prepare inputs
project = cs.find_project(project)
job = project.find_job(select2d_job_id)
path_to_cs_job = str(job.dir())
star_file_path = f"{relion_project_path}/{star_file_output_prefix}.star"

cmd = f"{pyem_path}csparc2star.py {path_to_cs_job}/particles_selected.cs {path_to_cs_job}/{job.uid}_passthrough_particles_selected.cs {star_file_path}"
print(f"Running command:\n{cmd}")

try:
    subprocess.run(cmd, shell=True, check=True)
    print(f"{star_file_path} successfully created")
except subprocess.CalledProcessError as e:
    print(f"Error occurred when running csparc2star.py: {e}")

# change mrc --> mrcs in starfile
try:
    subprocess.run(f"sed -i 's/.mrc/.mrcs/g' {star_file_path}", shell=True, check=True)
    print("STAR file updated to use MRCS extensions.")
except subprocess.CalledProcessError as e:
    print(f"Error occurred when modifying the STAR file (mrc --> mrcs): {e}")

# mkdir for mrc files (particles)
star_mrc_path = get_star_path(f"{relion_project_path}/{star_file_output_prefix}.star")
os.makedirs(f"{relion_project_path}/{star_mrc_path}", exist_ok=True)
print(f"Created directory for particle mrc files: {relion_project_path}/{star_mrc_path}")

# link and rename mrc files
try:
    cs_job_extract_path = os.path.join(project.dir(), star_mrc_path)
    target_path = os.path.join(relion_project_path, star_mrc_path)
    mrc_files = glob.glob(f"{cs_job_extract_path}/*.mrc")

    for mrc_file in mrc_files:
        target_file = os.path.join(target_path, os.path.basename(mrc_file))
        if not os.path.exists(target_file):
            os.symlink(mrc_file, target_file)

    # subprocess.run(f"ln -s {cs_job_extract_path}/*mrc -t {target_path}", shell=True, check=True)
    print("mrc files are linked successfully")

    # Rename .mrc files to .mrcs
    print("renaming back...")
    target_mrc_files = glob.glob(f"{target_path}/*.mrc")
    for mrc_file in target_mrc_files:
        if mrc_file.endswith(".mrc"):
            mrcs_file = mrc_file[:-4] + ".mrcs"
            # print(mrc_file, mrcs_file)
            os.rename(mrc_file, mrcs_file)

    print("Renaming MRC files to MRCS completed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error occurred during symlinking and renaming: {e}")
print("Done!")
