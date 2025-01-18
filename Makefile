PACKAGE_MGR=apt-get
PACKAGE_MGR_INSTALL_OPT=install -y
PACKAGE_MGR_INSTALL=$(PACKAGE_MGR) $(PACKAGE_MGR_INSTALL_OPT)
PYTHON_VER=3.9
PYTHON_BIN=python$(PYTHON_VER)
VENV_PATH=./cmsvenv
USR_ROOT=/usr/local
CMS_USER_GROUP=cmsuser

#Isolate: libsystemd-dev
# create group, copy, set perms

help:
	echo TODO

clean:
	rm -rf isolate

install-isolate:
	sudo apt update
	sudo $(PACKAGE_MGR_INSTALL) libcap-dev libsystemd-dev
	sudo groupadd $(CMS_USER_GROUP) || true
	sudo usermod -a -G cmsuser $(whoami)
	git clone https://github.com/ioi/isolate.git
	cd isolate && make isolate
	cd isolate && sudo cp ./isolate $(USR_ROOT)/bin/isolate
	sudo chgrp $(CMS_USER_GROUP) $(USR_ROOT)/bin/isolate
	sudo chmod 4750 $(USR_ROOT)/bin/isolate
	cd isolate && sudo cp ./default.cf $(USR_ROOT)/etc/isolate
	sudo chgrp $(CMS_USER_GROUP) $(USR_ROOT)/etc/isolate
	sudo chmod 640 $(USR_ROOT)/etc/isolate
	echo $(isolate --version)


python-apt-deps:
	sudo add-apt-repository -y ppa:deadsnakes/ppa
	sudo apt-get update
	sudo $(PACKAGE_MGR_INSTALL) $(PYTHON_BIN) $(PYTHON_BIN)-dev $(PYTHON_BIN)-venv \
	python3-pip

apt-deps:
	sudo $(PACKAGE_MGR_INSTALL) build-essential openjdk-17-jdk-headless fp-compiler \
    postgresql postgresql-client cppreference-doc-en-html \
    cgroup-lite libcap-dev zip libpq-dev libcups2-dev libyaml-dev \
    libffi-dev 

install-cms:
	$(PYTHON_BIN) -m venv $(VENV_PATH)
	export SETUPTOOLS_USE_DISTUTILS="stdlib" ; . $(VENV_PATH)/bin/activate ; pip3 install -r requirements.txt
	export SETUPTOOLS_USE_DISTUTILS="stdlib" ; . $(VENV_PATH)/bin/activate ; $(PYTHON_BIN) setup.py install

install: apt-deps install-isolate python-apt-deps install-cms
	echo "SUCCESS"
