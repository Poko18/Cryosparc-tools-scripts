# Download and install aspera-cli for linux
wget https://ak-delivery04-mul.dhe.ibm.com/sar/CMA/OSA/08q6g/0/ibm-aspera-cli-3.9.6.1467.159c5b1-linux-64-release.sh
chmod +x ibm-aspera-cli-3.9.6.1467.159c5b1-linux-64-release.sh
./ibm-aspera-cli-3.9.6.1467.159c5b1-linux-64-release.sh
export PATH=/home/ec2-user/.aspera/cli/bin:$PATH

# Download EMPIAR-10028 particles (~51GB)
ascp -QT -k3 -l 10000M -P33001 -i ~/.aspera/cli/etc/asperaweb_id_dsa.openssh emp_ext2@hx-fasp-1.ebi.ac.uk:/10028 .

# Alternatively use ftp server
wget -b -m ftp://ftp.ebi.ac.uk/empiar/world_availability/10028/data/Particles/
