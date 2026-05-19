PYTHON ?= python3
MAKEFILE_ABS := $(abspath $(lastword $(MAKEFILE_LIST)))
INSTALLER_DIR := $(dir $(MAKEFILE_ABS))
ROOT := $(abspath $(INSTALLER_DIR)../..)
BUILD_DIR := $(INSTALLER_DIR)build
DIST_DIR := $(INSTALLER_DIR)dist
INSTALL_PREFIX ?= /usr/local/bin

.PHONY: all clean install binary deb verify

all: $(BUILD_DIR)/lumen

$(BUILD_DIR)/lumen:
	@echo "[lumen] Generando binario standalone..."
	@mkdir -p $(BUILD_DIR) $(DIST_DIR)
	cd $(ROOT) && $(PYTHON) installer/linux/build.py
	@echo "[OK] Generado: $(BUILD_DIR)/lumen"

clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR) $(INSTALLER_DIR)__pycache__

install: $(BUILD_DIR)/lumen
	cp $(BUILD_DIR)/lumen $(INSTALL_PREFIX)/lumen
	@echo "[OK] Instalado en $(INSTALL_PREFIX)/lumen"

binary: $(BUILD_DIR)/lumen

deb: binary
	@echo "[lumen] Generando paquete .deb..."
	@mkdir -p $(BUILD_DIR)/deb/usr/bin $(BUILD_DIR)/deb/DEBIAN
	@cp $(BUILD_DIR)/lumen $(BUILD_DIR)/deb/usr/bin/lumen
	@chmod 755 $(BUILD_DIR)/deb/usr/bin/lumen
	@printf "Package: lumen-lang\nVersion: 0.1.0\nArchitecture: amd64\nMaintainer: Lumen Project\nDescription: Lumen language runtime\n" > $(BUILD_DIR)/deb/DEBIAN/control
	@dpkg-deb --build $(BUILD_DIR)/deb $(DIST_DIR)/lumen-lang_0.1.0_amd64.deb
	@echo "[OK] Paquete .deb: $(DIST_DIR)/lumen-lang_0.1.0_amd64.deb"

verify:
	@$(BUILD_DIR)/lumen --version
	@echo "[OK] Verificación exitosa"
