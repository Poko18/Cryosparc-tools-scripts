from dotenv import dotenv_values
from cryosparc.tools import CryoSPARC
import argparse
import os

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run CryoDRGN in cryosparc')
parser.add_argument('project', type=str, help='Name of project to run the job in')
parser.add_argument('workspace', type=str, help='Name of workspace to run the job in')
parser.add_argument('refinement_job_id', type=str, help='ID of the refinement job')
parser.add_argument('downsample_job_id', type=str, help='ID of the downsample particle job')
parser.add_argument('initial_particle_size', type=str, help='Initial particle size before downsampling')

parser.add_argument('--particles', type=str, help='path to downsampled particles')
parser.add_argument('--particle_subset', type=int, help='ID of the job of downsampled particles')
parser.add_argument('--downsampled_particles_job_id', type=str, help='ID of the job of downsampled particles')
parser.add_argument('--downsample_size', default=128, type=int, help='downsampled particle size (default: 128)')
parser.add_argument('--title', type=str, default='cryodrgn', help='Title for job (default: "crYOLO Picks")')
parser.add_argument('--baseport', type=str, default=39000, help='Cryosparc baseport (default: 39000)')
parser.add_argument('--numexpr_max_threads', type=str, default='32', help='numexpr max threads (default: 32)')
args = parser.parse_args()


initial_size=args.initial_particle_size # get from map?
downsampled_size=args.downsample_size

os.environ['NUMEXPR_MAX_THREADS'] = args.numexpr_max_threads

# Load login credentials from .env file
env_vars = dotenv_values('.env')
license = env_vars['CRYOSPARC_LICENSE_ID']
host = env_vars['CRYOSPARC_HOST']
email = env_vars['CRYOSPARC_EMAIL']
password = env_vars['CRYOSPARC_PASSWORD']

# Connect to CryoSPARC instance
cs = CryoSPARC(
    license=license,
    host=host,
    base_port=args.baseport,
    email=email,
    password=password
)

# Create external job
project=cs.find_project(args.project)
job=project.create_external_job(args.workspace, title=args.title)

# TO DO - load poses and ctf directly from connected job
#job.connect("particles", args.refinement_job_id, "particles", slots=["blob", "alignments3D", "ctf"])
#job.connect("particles", args.downsample_job_id, "particles", slots=["blob", "alignments3D", "ctf"])

# Start job
job.log(f"Starting job - {job.uid}")
job.start(status="running")

# Find particles.cs file
refinement_job = project.find_job(args.refinement_job_id)
particle_file_list = refinement_job.list_files()
particles_file = sorted([file for file in particle_file_list if file.endswith("particles.cs") and not file.endswith("passthrough_particles.cs") ])[-1]
particles_file_path=f"{str(refinement_job.dir())}/{particles_file}"
# Copy particles file
particles_file_final_path=f"{job.dir()}/{particles_file}"
#job.cp(particles_file_path,particles_file_final_path)
project.symlink(particles_file_path,particles_file_final_path)

# Find downsample.cs file
downsample_job = project.find_job(args.downsample_job_id)
downsample_file_path=f"{str(downsample_job.dir())}/downsampled_particles.cs"
# Copy downsample file
downsample_file_final_path=f"{job.dir()}/downsampled_particles.cs"
job.cp(downsample_file_path,downsample_file_final_path)
project.symlink(downsample_file_path,downsample_file_final_path)

# Symlink downsample job (for particles)
#print(f"symlinking {str(downsample_job.dir())} to {job.dir()}")
#project.symlink(str(downsample_job.dir()), f"{job.dir()}/J304")
#print(f"files - {job.list_files()}")

particles = job.load_input("particles", ["blob"]).rows()
number_of_particles=len(particles)
if args.particle_subset:
    subset=args.particle_subset
else:
    subset=number_of_particles
print(f"working with a subset of: {subset} of total {number_of_particles} particles!")

# Create subset ind file
ind_file=f"ind{subset}.pkl"
job.subprocess(
    f"cryodrgn_utils select_random {number_of_particles} -n {subset} -o {ind_file}".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True
)

# Parse poses and ctf
job.subprocess(
    f"cryodrgn parse_pose_csparc {particles_file} -D {initial_size} -o pose.pkl".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True
)

job.subprocess(
    f"cryodrgn parse_ctf_csparc {particles_file} -o ctf.pkl".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True
)

# Start training
# TO DO add multigpus, lazy loading?, 
job.subprocess(
    f"cryodrgn train_vae downsampled_particles.cs --ctf ctf.pkl --ind ind{subset}.pkl --poses pose.pkl --zdim 8 -n 30 --datadir {project.dir()} -o 00_vae128".split(" "),
    cwd=job.dir(),
    mute=False,
    checkpoint=True
)

print("done")
job.stop()