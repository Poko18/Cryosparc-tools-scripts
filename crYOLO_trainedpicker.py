import argparse
from dotenv import dotenv_values
from cryosparc.tools import CryoSPARC
from cryosparc import star
from cryosparc.dataset import Dataset
from io import StringIO
import numpy as np
from numpy.core import records

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run crYOLO particle picking on a set of micrographs within CryoSPARC.')
parser.add_argument('project', type=str, help='Name of project to run job in')
parser.add_argument('workspace', type=str, help='Name of workspace to run job in')
parser.add_argument('curate_exposures_job_id', type=str, help='ID of job that curated the micrographs')
parser.add_argument('training_particles_job_id', type=str, help='ID of job with picked particles for training')
parser.add_argument('box_size', type=int, help='Box size for particle picking (in Angstroms)')
parser.add_argument('--title', type=str, default='crYOLO trained picks', help='Title for job (default: "crYOLO Picks")')
parser.add_argument('--lowpass', type=float, default=0.2, help='Low pass filter cutoff (default: 0.2)')
parser.add_argument('--threshold', type=float, default=0.1, help='Threshold for particle picking (default: 0.1)')
parser.add_argument('--baseport', type=str, default=39000, help='Cryosparc baseport')
parser.add_argument('--batch_size', type=str, default="2", help='Set crYOLO training batch size (default: 2)')
parser.add_argument('--pretrained_weights', type=str, default="", help='Start training from pretrained weights (default: "")')
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

# Connect micrographs to the job and add output
job.connect("train_micrographs", args.curate_exposures_job_id, "split_0", slots=["micrograph_blob"])
job.connect("train_particles", args.training_particles_job_id, "particles_selected", slots=["location"])
job.connect("all_micrographs", args.curate_exposures_job_id, "split_0", slots=["micrograph_blob"])
job.connect("all_micrographs", args.curate_exposures_job_id, "remainder", slots=["micrograph_blob"])
job.add_output("particle", "predicted_particles", slots=["location", "pick_stats"])

# Start the job and set its status to "running"
job.start(status="running")

# Create directories and symlink the data
job.mkdir("full_data")
job.mkdir("train_image")
job.mkdir("train_annot")
all_micrographs = job.load_input("all_micrographs", ["micrograph_blob"])
train_micrographs = job.load_input("train_micrographs", ["micrograph_blob"])
for mic in all_micrographs.rows():
    source = mic["micrograph_blob/path"]
    target = job.uid + "/full_data/" + source.split("/")[-1]
    project.symlink(source, target)
for mic in train_micrographs.rows():
    source = mic["micrograph_blob/path"]
    target = job.uid + "/train_image/" + source.split("/")[-1]
    project.symlink(source, target)

# Load the training particle locations. Split them up my micrograph path.
# Compute the pixel locations and save them to a star file in this format
job.mkdir("train_annot/STAR")
train_particles = job.load_input("train_particles", ["location"])

for micrograph_path, particles in train_particles.split_by("location/micrograph_path").items():
    micrograph_name = micrograph_path.split("/")[-1]
    star_file_name = micrograph_name.rsplit(".", 1)[0] + ".star"

    mic_w = particles["location/micrograph_shape"][:, 1]
    mic_h = particles["location/micrograph_shape"][:, 0]
    center_x = particles["location/center_x_frac"]
    center_y = particles["location/center_y_frac"]
    location_x = center_x * mic_w
    location_y = center_y * mic_h

    outfile = StringIO()
    star.write(
        outfile,
        records.fromarrays([location_x, location_y], names=["rlnCoordinateX", "rlnCoordinateY"]),
    )
    outfile.seek(0)
    job.upload("train_annot/STAR/" + star_file_name, outfile)

# Configure crYOLO
job.subprocess(
    (
        f"cryolo_gui.py config config_cryolo.json {args.box_size} "
        "--train_image_folder train_image "
        "--train_annot_folder train_annot "
        f"--batch_size {args.batch_size} "
        f"--pretrained_weights {args.pretrained_weights}"
    ).split(" "),
    cwd=job.dir(),
)

# Training
#To run the training on GPU 0 with 5 warmup-epochs and an early stop
# of 15 navigate to the folder with config_cryolo.json file, train_image folder etc.
job.subprocess(
    "cryolo_train.py -c config_cryolo.json -w 5 -g 0 -e 15".split(" "), #
    cwd=job.dir(),
    mute=True,
    checkpoint=True,
    checkpoint_line_pattern=r"Epoch \d+/\d+",  # e.g., "Epoch 42/200"
)

# Run particle picking job
job.mkdir("boxfiles")
job.subprocess(
    "cryolo_predict.py -c config_cryolo.json -w cryolo_model.h5 -i full_data -g 0 -o boxfiles -t 0.3".split(" "),
    cwd=job.dir(),
    mute=True,
    checkpoint=True,
)

# Fill in a dummy NCC score so that the results may be inspected with an Inspect Picks job.
output_star_folder = "STAR"
all_predicted = []
for mic in all_micrographs.rows():
    micrograph_path = mic["micrograph_blob/path"]
    micrograph_name = micrograph_path.split("/")[-1]
    height, width = mic["micrograph_blob/shape"]

    starfile_name = micrograph_name.rsplit(".", 1)[0] + ".star"
    starfile_path = "boxfiles/STAR/" + starfile_name
    locations = star.read(job.dir() / starfile_path)[""]
    center_x = locations["rlnCoordinateX"] / width
    center_y = locations["rlnCoordinateY"] / height

    predicted = job.alloc_output("predicted_particles", len(locations))
    predicted["location/micrograph_uid"] = mic["uid"]
    predicted["location/micrograph_path"] = mic["micrograph_blob/path"]
    predicted["location/micrograph_shape"] = mic["micrograph_blob/shape"]
    predicted["location/center_x_frac"] = center_x
    predicted["location/center_y_frac"] = center_y
    predicted["pick_stats/ncc_score"] = 0.5

    all_predicted.append(predicted)

# Save particle locations and stop job
job.save_output("predicted_particles", Dataset.append(*all_predicted))
job.stop()