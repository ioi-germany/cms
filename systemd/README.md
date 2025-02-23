# Systemd Service Files

These files can be used to integrate the cmsLogService and cmsResourceService
in an server setup with systemd.

The variables $CMS_USER and $CMS_VENV_INSTALLATION_DIR have to be replaced by the user which should run the cms and the directory which contains the python virtual environment (and therefore the start scripts for the Log and Resource Services).

The files have to be copied into `/etc/systemd/system/`.
