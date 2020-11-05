build-libdmtx:
	yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
	yum install -y libdmtx
	mkdir -p "$(ARTIFACTS_DIR)/python"
	python -m pip install pylibdmtx -t "$(ARTIFACTS_DIR)/python"