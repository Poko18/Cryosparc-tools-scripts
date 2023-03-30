import argparse
from dotenv import dotenv_values
from cryosparc.tools import CryoSPARC
from cryosparc import star
from cryosparc.dataset import Dataset

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run crYOLO particle picking on a set of micrographs within CryoSPARC.')
parser.add_argument('project', type=str, help='Name of project to run job in')
parser.add_argument('workspace', type=str, help='Name of workspace to run job in')
parser.add_argument('curate_exposures_job_id', type=str, help='ID of job that curated the micrographs')
parser.add_argument('box_size', type=int, help='Box size for particle picking (in Angstroms)')
parser.add_argument('model_path', type=str, help='Path to crYOLO model')

parser.add_argument('--title', type=str, default='crYOLO Picks', help='Title for job (default: "crYOLO Picks")')
parser.add_argument('--lowpass', type=float, default=0.2, help='Low pass filter cutoff (default: 0.2)')
parser.add_argument('--threshold', type=float, default=0.001, help='Threshold for particle picking (default: 0.001)')
parser.add_argument('--baseport', type=str, default=39000, help='Cryosparc baseport (default: 39000)')
args = parser.parse_args()

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

# Find project and create job
project = cs.find_project(args.project)
job = project.create_external_job(args.workspace, title=args.title)
curate_job = project.find_job(args.curate_exposures_job_id)

# Connect micrographs to the job and add output
job.connect("all_micrographs", args.curate_exposures_job_id, "exposures_accepted", slots=["micrograph_blob"])
job.add_output("particle", "predicted_particles", slots=["location", "pick_stats"])

# Wait for all previous jobs to finish
job.start(status="waiting")
job.log(f"Waiting for job {args.curate_exposures_job_id} to finish.")
curate_job.wait_for_status(status="completed")
job.stop()

# Start the job and set its status to "running"
job.log(f"Starting job - {job.uid}")
job.start(status="running")

# Create directory and symlink the micrographs
job.mkdir("full_data")
all_micrographs = job.load_input("all_micrographs", ["micrograph_blob"])
for mic in all_micrographs.rows():
    source = mic["micrograph_blob/path"]
    target = job.uid + "/full_data/" + source.split("/")[-1]
    project.symlink(source, target)

# Configure crYOLO
job.subprocess(
    f"cryolo_gui.py config config_cryolo.json {args.box_size} --filter LOWPASS --low_pass_cutoff {args.lowpass}".split(" "),
    cwd=job.dir(),
    mute=True,
    checkpoint=True,
)

# Run particle picking job
job.subprocess(
    f"cryolo_predict.py -c config_cryolo.json -w {args.model_path} -i full_data -g 0 -o boxfiles -t {args.threshold}".split(" "),
    cwd=job.dir(),
    mute=True,
    checkpoint=True,
)

# Fill CrYOLO threshold as NCC and power score so that the results may be inspected and filtered with an Inspect Picks job.
output_star_folder = "STAR"
all_predicted = []

starfile_path = "boxfiles/CRYOSPARC/cryosparc.star" 
locations = star.read(job.dir() / starfile_path)[""]

for mic in all_micrographs.rows():
    micrograph_path = mic["micrograph_blob/path"]
    micrograph_name = micrograph_path.split("/")[-1]
    height, width = mic["micrograph_blob/shape"]

    center_x = locations[locations['rlnMicrographName'] == micrograph_name]['rlnCoordinateX'] / width
    center_y = locations[locations['rlnMicrographName'] == micrograph_name]['rlnCoordinateY'] / height
    threshold = locations[locations['rlnMicrographName'] == micrograph_name]['rlnAutopickFigureOfMerit']

    predicted = job.alloc_output("predicted_particles", len(locations[locations['rlnMicrographName'] == micrograph_name]))
    predicted["location/micrograph_uid"] = mic["uid"]
    predicted["location/micrograph_path"] = mic["micrograph_blob/path"]
    predicted["location/micrograph_shape"] = mic["micrograph_blob/shape"]
    predicted["location/center_x_frac"] = center_x
    predicted["location/center_y_frac"] = center_y
    predicted["pick_stats/ncc_score"] = threshold
    predicted["pick_stats/power"] = threshold
    all_predicted.append(predicted)

# Save particle locations and stop job
job.save_output("predicted_particles", Dataset.append(*all_predicted))
job.stop()