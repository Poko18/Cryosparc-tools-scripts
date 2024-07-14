import argparse
import os

from cryosparc.dataset import Dataset
from cryosparc.tools import CryoSPARC
from dotenv import dotenv_values

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run CryoDRGN in cryosparc. Before use, run C1 homogenous refinement job and downsample job on the same particle stack")
parser.add_argument("project", type=str, help="Name of project to run the job in")
parser.add_argument("workspace", type=str, help="Name of workspace to run the job in")
parser.add_argument("refinement_job_id", type=str, help="ID of the refinement job")
parser.add_argument("downsample_job_id", type=str, help="ID of the downsample particle job")

parser.add_argument("--particle_subset", type=int, help="ID of the job of downsampled particles")
parser.add_argument("--epochs", default=50, type=int, help="Number of training epochs (default: 50)")
parser.add_argument("--batch", default=8, type=int, help="Training batch size (default: 8)")
parser.add_argument("--zdim", default=8, type=int, help="Number of zdim (default: 8)")
parser.add_argument("--multigpu", type=str, help="Write which GPUs to use (2,3)")

parser.add_argument("--title", type=str, default="cryodrgn", help="Title for job (default: cryodrgn)")
parser.add_argument("--baseport", type=str, default=39000, help="Cryosparc baseport (default: 39000)")
parser.add_argument(
    "--numexpr_max_threads",
    type=str,
    default="32",
    help="numexpr max threads (default: 32)",
)
args = parser.parse_args()

# TO DO load poses and ctf directly from connected job
# TO DO add volume series output and traversal images

os.environ["NUMEXPR_MAX_THREADS"] = args.numexpr_max_threads

# Load login credentials from .env file
env_vars = dotenv_values(".env")
license = env_vars["CRYOSPARC_LICENSE_ID"]
host = env_vars["CRYOSPARC_HOST"]
email = env_vars["CRYOSPARC_EMAIL"]
password = env_vars["CRYOSPARC_PASSWORD"]

# Connect to CryoSPARC instance
cs = CryoSPARC(license=license, host=host, base_port=args.baseport, email=email, password=password)

# Create external job
project = cs.find_project(args.project)
job = project.create_external_job(args.workspace, title=args.title)

# job.connect("particles", args.refinement_job_id, "particles", slots=["blob", "alignments3D", "ctf"])
job.connect(
    "particles",
    args.downsample_job_id,
    "particles",
    slots=["blob", "alignments3D", "ctf"],
)
job.add_output("volume", "series_pc1", slots=["series"])
job.add_output("volume", "series_pc2", slots=["series"])

# Wait for other jobs to finish
job.start(status="waiting")
refinement_job = project.find_job(args.refinement_job_id)
downsample_job = project.find_job(args.downsample_job_id)
job.log(f"Waiting for job {args.refinement_job_id} and {args.downsample_job_id} to finish.")
refinement_job.wait_for_status(status="completed")
downsample_job.wait_for_status(status="completed")
job.stop()

# Start job
job.log(f"Starting job - {job.uid}")
job.start(status="running")

# Find particles.cs file
particle_file_list = refinement_job.list_files()
particles_file = sorted([file for file in particle_file_list if file.endswith("particles.cs") and not file.endswith("passthrough_particles.cs")])[-1]
particles_file_path = f"{str(refinement_job.dir())}/{particles_file}"
# Link particles file
particles_file_final_path = f"{job.dir()}/{particles_file}"
project.symlink(particles_file_path, particles_file_final_path)

# Find downsample.cs file
downsample_file_path = f"{str(downsample_job.dir())}/downsampled_particles.cs"
# Link downsample file
downsample_file_final_path = f"{job.dir()}/downsampled_particles.cs"
project.symlink(downsample_file_path, downsample_file_final_path)

# Extract pixel and particle size
refinement_file = Dataset.load(particles_file_final_path)
initail_apix = refinement_file["blob/psize_A"][0]
initial_particle_size = refinement_file["blob/shape"][0][0]

downsample_file = Dataset.load(downsample_file_final_path)
downsample_apix = downsample_file["blob/psize_A"][0]
downsample_particle_size = downsample_file["blob/shape"][0][0]

job.log(f"Initial Pixel Size: {initail_apix} angstroms")
job.log(f"Initial Particle Size: {initial_particle_size} pixels")
job.log(f"Downsampled Pixel Size: {downsample_apix} angstroms")
job.log(f"Downsampled Particle Size: {downsample_particle_size} pixels")

# Number of particles
particles = job.load_input("particles", ["blob"]).rows()
number_of_particles = len(particles)
if args.particle_subset:
    subset = args.particle_subset
else:
    subset = number_of_particles
job.log(f"working with a subset of: {subset} of total {number_of_particles} particles!")

# Create subset ind file
ind_file = f"ind{subset}.pkl"
job.subprocess(
    f"cryodrgn_utils select_random {number_of_particles} -n {subset} -o {ind_file}".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True,
)

# Parse poses and ctf
job.subprocess(
    f"cryodrgn parse_pose_csparc {particles_file} -D {initial_particle_size} -o pose.pkl".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True,
)

job.subprocess(
    f"cryodrgn parse_ctf_csparc {particles_file} -o ctf.pkl".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True,
)

multigpu = ""
gpu_numbers = ""
if args.multigpu:
    multigpu = f" --multigpu"
    gpu_numbers = f"CUDA_VISIBLE_DEVICES={args.multigpu} "
    job.log(f"Running on multiple gpus - {gpu_numbers}")

# Start training
job.subprocess(
    f"{gpu_numbers}cryodrgn train_vae downsampled_particles.cs --ctf ctf.pkl --ind ind{subset}.pkl --poses pose.pkl --zdim {args.zdim} -n {args.epochs} -b {args.batch} --datadir {project.dir()} -o cryodrgn{multigpu}".split(
        " "
    ),
    cwd=job.dir(),
    mute=False,
    checkpoint=True,
)

# Analysis
cryodrgn_output = f"{job.dir()}/cryodrgn"
analyze_epoch = int(args.epochs) - 1
cryodrgn_analyze_output = f"{job.dir()}/cryodrgn_analyze_{analyze_epoch}"

job.subprocess(
    f"cryodrgn analyze {cryodrgn_output} {analyze_epoch} -o {cryodrgn_analyze_output} --Apix {downsample_apix}".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True,
)
job.log(f"Results can be found in: {cryodrgn_analyze_output}")
job.log(f"z_pca:")
job.log_plot(f"{cryodrgn_analyze_output}/z_pca.png", "z_pca")

job.log(f"PC1 traversal:")
job.log_plot(f"{cryodrgn_analyze_output}/pc1/pca_traversal.png", "pc1_traversal")

job.log(f"PC2 traversal:")
job.log_plot(f"{cryodrgn_analyze_output}/pc2/pca_traversal.png", "pc2_traversal")
# TO DO
# import shutil

# folder_to_zip = f'{cryodrgn_analyze_output}/pc1'
# zip_filename = f'{cryodrgn_analyze_output}/volume_series_pc1.zip'
# shutil.make_archive(zip_filename.split('.zip')[0], 'zip', folder_to_zip)
# job.save_output("series_pc1", zip_filename)

# folder_to_zip = f'{cryodrgn_analyze_output}/pc2'
# zip_filename = f'{cryodrgn_analyze_output}/volume_series_pc2.zip'
# shutil.make_archive(zip_filename.split('.zip')[0], 'zip', folder_to_zip)
# job.save_output("series_pc2", zip_filename)

job.log("done")
job.stop()
