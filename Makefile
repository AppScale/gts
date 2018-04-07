#
# Makefile currently only performs some release
# activities, version bump and release notes generation
#

.PHONY: bump-major bump-minor bump-patch release-notes help all

all: help

help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-10s\033[0m- %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bump-major: ## Bump the major version number for AppScale
	util/bump_version.sh major

bump-minor: ## Bump the minor version number for AppScale
	util/bump_version.sh minor

bump-patch: ## Bump the patch version number for AppScale
	util/bump_version.sh patch

release-notes: ## Generate release notes for a new release
	util/gen_release_notes.sh

