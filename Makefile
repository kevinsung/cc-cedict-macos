# CC-CEDICT -> macOS Dictionary.app
#
# One build, start to finish, on a Mac: fetch the latest CC-CEDICT from MDBG,
# generate a Dictionary Development Kit source project, and compile it into
# CC-CEDICT.dictionary.
#
#   make            fetch + generate + compile the bundle
#   make install    copy it into ~/Library/Dictionaries
#   make check      tests, lint, and RelaxNG validation

PYTHON      := python3
RUN         := PYTHONPATH=src $(PYTHON)

SRC_URL     := https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
DATA_DIR    := data
SRC_GZ      := $(DATA_DIR)/cedict.txt.gz
SRC_TXT     := $(DATA_DIR)/cedict.txt

BUILD_DIR   := build
OUT_DIR     := $(BUILD_DIR)/CC-CEDICT.dictionary-src
XML         := $(OUT_DIR)/CCCEDICT.xml
SAMPLE_XML  := $(BUILD_DIR)/sample.xml

SCHEMA_DIR  := schema
SCHEMA      := $(SCHEMA_DIR)/AppleDictionarySchema.rng

DICT_NAME   := CC-CEDICT
DDK_DIR     := /Applications/Utilities/Dictionary Development Kit
BUNDLE      := $(OUT_DIR)/objects/$(DICT_NAME).dictionary
DEST        := $(HOME)/Library/Dictionaries

# -s 0 suppresses supplementary/inflection key generation. That machinery is
# English morphology (plurals, verb forms); for Chinese it only makes the index
# larger and the build slower.
DICT_BUILD_OPTS := -s 0

.DEFAULT_GOAL := all

# The DDK step is not parallel-safe, and the preflight check must not race the
# compile it is guarding.
.NOTPARALLEL:

# Two sub-invocations so the freshness check finishes before any file rule reads
# the timestamp of $(SRC_TXT).
.PHONY: all
all:
	@$(MAKE) fetch
	@$(MAKE) bundle

# ------------------------------------------------------------------ fetching

# Always asks MDBG whether there is a newer edition. Downloads to a temporary
# name because `curl -o` truncates its output file, which would destroy the
# cached copy on a 304 or a dropped connection. An unchanged upstream leaves
# every timestamp alone, so nothing downstream rebuilds.
.PHONY: fetch
fetch:
	@mkdir -p $(DATA_DIR)
	@if [ -f $(SRC_GZ) ]; then tc="-z $(SRC_GZ)"; else tc=""; fi; \
	 if ! curl -sSL --fail $$tc -o $(SRC_GZ).new $(SRC_URL); then \
	   rm -f $(SRC_GZ).new; \
	   if [ -f $(SRC_GZ) ]; then \
	     echo "warning: could not reach MDBG; building from the cached copy"; \
	   else \
	     echo "could not download $(SRC_URL)"; exit 1; \
	   fi; \
	 fi
	@if [ -s $(SRC_GZ).new ]; then \
	   gzip -t $(SRC_GZ).new && mv $(SRC_GZ).new $(SRC_GZ) && echo "fetched a newer edition"; \
	 else rm -f $(SRC_GZ).new; fi
	@if [ ! -f $(SRC_TXT) ] || [ $(SRC_GZ) -nt $(SRC_TXT) ]; then \
	   gunzip -c $(SRC_GZ) > $(SRC_TXT); fi

# So that `make source` (or any target needing the data) works from a cold
# checkout; `fetch` writes both files.
$(SRC_GZ) $(SRC_TXT):
	@$(MAKE) fetch

# ---------------------------------------------------------------- generating

.PHONY: source
source: $(XML)

$(XML): $(SRC_TXT) $(wildcard src/cccedict/*.py) $(wildcard assets/*)
	$(RUN) -m cccedict.build --source $(SRC_TXT) --output $(OUT_DIR)

# ----------------------------------------------------------------- compiling

.PHONY: bundle
bundle: check-ddk $(BUNDLE)

# Run from inside the source project so the DDK writes objects/ there and the
# arguments stay the bare filenames it expects.
$(BUNDLE): $(XML)
	@echo "Building $(DICT_NAME).dictionary — this takes a few minutes for 122k entries."
	cd $(OUT_DIR) && "$(DDK_DIR)/bin/build_dict.sh" $(DICT_BUILD_OPTS) \
		"$(DICT_NAME)" CCCEDICT.xml CCCEDICT.css Info.plist
	@echo "Done. Now run: make install"

.PHONY: check-ddk
check-ddk:
	@if [ ! -d "$(DDK_DIR)" ]; then \
		echo "This build requires macOS with the Dictionary Development Kit, which"; \
		echo "was not found at:"; \
		echo "  $(DDK_DIR)"; \
		echo ""; \
		echo "Install it from 'Additional Tools for Xcode':"; \
		echo "  https://developer.apple.com/download/all/?q=Additional%20Tools"; \
		echo "Download the disk image matching your Xcode version, then copy"; \
		echo "'Dictionary Development Kit' from Utilities into /Applications/Utilities/."; \
		echo ""; \
		echo "Or use the community mirror:"; \
		echo "  https://github.com/SebastianSzturo/Dictionary-Development-Kit"; \
		echo ""; \
		echo "Xcode command line tools are also required: xcode-select --install"; \
		exit 1; \
	fi
	@echo "Dictionary Development Kit found."

# ----------------------------------------------------------------- installing

.PHONY: install
install: all
	mkdir -p "$(DEST)"
	rm -rf "$(DEST)/$(DICT_NAME).dictionary"
	ditto --noextattr --norsrc "$(BUNDLE)" "$(DEST)/$(DICT_NAME).dictionary"
	touch "$(DEST)"
	@echo "Installed to $(DEST)/$(DICT_NAME).dictionary"
	@echo "Open Dictionary.app > Settings and enable CC-CEDICT (relaunch if it does not appear)."

.PHONY: uninstall
uninstall:
	rm -rf "$(DEST)/$(DICT_NAME).dictionary"
	touch "$(DEST)"
	@echo "Removed $(DEST)/$(DICT_NAME).dictionary"

# ---------------------------------------------------------------- validating

.PHONY: schema
schema: $(SCHEMA)

$(SCHEMA):
	$(RUN) -m cccedict.schema --target $(SCHEMA_DIR)

# Full-file RelaxNG validation against Apple's own schema: ~20s and ~1.1 GB of
# memory for the complete 80 MB document.
.PHONY: validate
validate: $(XML) $(SCHEMA)
	xmllint --noout --relaxng $(SCHEMA) $(XML)

# Front matter + the first 5,000 entries + a deterministic random 5,000. Use
# this for quick iteration; it runs in about a second.
.PHONY: validate-sample
validate-sample: $(XML) $(SCHEMA)
	$(RUN) -m cccedict.sample $(XML) $(SAMPLE_XML)
	xmllint --noout --relaxng $(SCHEMA) $(SAMPLE_XML)

.PHONY: wellformed
wellformed: $(XML)
	xmllint --noout $(XML)

.PHONY: lint
lint: $(XML)
	$(RUN) -m cccedict.lint $(XML)

.PHONY: test
test:
	$(RUN) -m unittest discover -s tests

# Everything worth checking about the generated XML. Not on the default path:
# the full RelaxNG pass alone is ~20s and ~1.1 GB.
.PHONY: check
check: test wellformed lint validate
	@echo ""
	@echo "All checks passed."

# ------------------------------------------------------------------ cleaning

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)

.PHONY: distclean
distclean: clean
	rm -rf $(DATA_DIR) $(SCHEMA_DIR)
