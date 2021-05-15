build-OpenSlide:
	yum install -y git autoconf, automake, libtool, and pkg-config
	yum install -y libjpeg-turbo-devel openjpeg2-devel libtiff-devel cairo-devel gdk-pixbuf2-devel sqlite-devel libxml2-devel
	mkdir -p "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libcairo.so.2 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libxml2.so.2 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libopenjp2.so.7 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libtiff.so.5 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libpng15.so.15 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libgdk_pixbuf-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libjpeg.so.62 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libEGL.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libfontconfig.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libfreetype.so.6 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libglib-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libgmodule-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libgobject-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libgthread-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libgio-2.0.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libmount.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libpixman-1.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libxcb-shm.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libxcb.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libxcb-render.so.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libXrender.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libX11.so.6 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libXext.so.6 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libGL.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/liblzma.so.5 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libjbig.so.2.0 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libblkid.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libuuid.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libexpat.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libbz2.so.1 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libGLdispatch.so.0  "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libXau.so.6 "$(ARTIFACTS_DIR)/lib"
	cp /usr/lib64/libGLX.so.0 "$(ARTIFACTS_DIR)/lib"

	git clone https://github.com/VanAndelInstitute/openslide.git
	cd openslide \
	&& autoreconf -i \
	&& ./configure --prefix=$(ARTIFACTS_DIR) \
	&& make \
	&& make install
	mkdir -p "$(ARTIFACTS_DIR)/python"
	python -m pip install --no-deps openslide-python -t "$(ARTIFACTS_DIR)/python"
