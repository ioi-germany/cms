PACKAGE_MGR=apt-get
PACKAGE_MGR_INSTALL_OPT=install -y
PACKAGE_MGR_INSTALL=$(PACKAGE_MGR) $(PACKAGE_MGR_INSTALL_OPT)

PYTHON_VER=3.9
PYTHON_BIN=python$(PYTHON_VER)
VENV_PATH=./cmsvenv

USR_ROOT=/usr/local
CMS_USER_GROUP=cmsuser

help: ## Show this help message
	@echo "Help: Build and install cms on the current machine"
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

ifeq "$(shell whoami)" "root"
assert-not-root:
	$(error Do not use sudo before make)
else
assert-not-root:
endif

clean:
	sudo rm -rf isolate

install-isolate:
	sudo apt update
	sudo $(PACKAGE_MGR_INSTALL) libcap-dev libsystemd-dev pkg-config
	sudo groupadd $(CMS_USER_GROUP) || true
	sudo usermod -a -G $(CMS_USER_GROUP) $(shell whoami)
	git clone https://github.com/ioi/isolate.git
	cd isolate && sudo make install
	cd isolate && sudo cp -rf systemd/* /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable isolate.service
	sudo systemctl start isolate.service
	isolate --version
	sudo rm -rf isolate

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

assert-isolate-functional:
	sudo -E -u $(shell whoami) isolate --cg --init
	sudo -E -u $(shell whoami) isolate --cg --cleanup
	@echo isolate is functional

install: assert-not-root apt-deps install-isolate python-apt-deps install-cms assert-isolate-functional ## Install cms (inclduing isolate v2) in virtual environment
	@echo "SUCCESS"

install-network: ## Install network packages for web server
	sudo $(PACKAGE_MGR_INSTALL) nginx-full

install-tex: ## Install latex related packages for statement compilation 
	sudo $(PACKAGE_MGR_INSTALL) texlive-latex-recommended texlive-fonts-extra \
	texlive-fonts-recommended texlive-formats-extra texlive-lang-english \
	texlive-lang-german texlive-luatex texlive-science

install-full: install install-network install-tex ## Install the complete cms suite including web server and statement compilation capability

