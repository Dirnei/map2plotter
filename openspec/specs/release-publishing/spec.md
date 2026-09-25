# release-publishing Specification

## Purpose

Defines how map2plotter versions and releases are created from its commit history, and which Docker images are published to the GitHub Container Registry, and when.

## Requirements

### Requirement: Release pull request from Conventional Commits
On every push to `main`, the project SHALL maintain one open release pull request, created and updated automatically. The version it proposes SHALL follow Semantic Versioning, derived from the Conventional Commits merged since the last release:
- `fix:` bumps the patch version
- `feat:` bumps the minor version
- a breaking change (`!` after the type, or a `BREAKING CHANGE` footer) bumps the major version

Other types (`docs:`, `refactor:`, `ci:`, `test:`, `chore:`) SHALL NOT trigger a release on their own. The release pull request SHALL update the package version in `pyproject.toml` and add an entry for the new version at the top of `CHANGELOG.md`, listing the commits grouped by type. The first release SHALL be 1.0.0.

#### Scenario: Feature merged
- **WHEN** the latest release is 1.0.0 and a commit `feat: add a new theme` is pushed to `main`
- **THEN** an open release pull request proposes version 1.1.0, sets `version = "1.1.0"` in `pyproject.toml` and adds a 1.1.0 entry to `CHANGELOG.md` that lists the commit under Features

#### Scenario: Only documentation changed
- **WHEN** the only commit since the latest release is `docs: fix a typo`
- **THEN** no release pull request proposes a new version

#### Scenario: First release
- **WHEN** release automation runs for the first time on `main`
- **THEN** the release pull request proposes version 1.0.0, and its release notes list the map2plotter commits made since the fork from maptoposter

### Requirement: Release created by merging the release pull request
Merging the release pull request SHALL create a git tag `v<version>` and a published GitHub release with the same name, whose notes are the new `CHANGELOG.md` entry. No release SHALL be created without that merge.

#### Scenario: Release PR merged
- **WHEN** the release pull request for 1.1.0 is merged into `main`
- **THEN** the tag `v1.1.0` and a GitHub release "v1.1.0" exist, and the installed package reports version 1.1.0

### Requirement: Docker image published for each release
When, and only when, a release is created, the project SHALL build the Docker image from the release commit and push it to `ghcr.io/<owner>/map2plotter`, with the owner in lowercase. It SHALL be tagged `<major>.<minor>.<patch>`, `<major>.<minor>`, `<major>` and `latest`. The image SHALL carry the OCI labels `org.opencontainers.image.version` (the release version), `org.opencontainers.image.source` (the repository URL) and `org.opencontainers.image.licenses` (`MIT`). Pushes to `main` that do not create a release SHALL NOT publish or overwrite any image tag.

#### Scenario: Release publishes image
- **WHEN** release 1.1.0 is created
- **THEN** `ghcr.io/dirnei/map2plotter` has the tags `1.1.0`, `1.1`, `1` and `latest`, all pointing to the same image, and the image's `org.opencontainers.image.version` label is `1.1.0`

#### Scenario: Ordinary push does not publish
- **WHEN** a commit that does not merge the release pull request is pushed to `main`
- **THEN** no image tag in `ghcr.io/dirnei/map2plotter` changes

#### Scenario: Version inside the image
- **WHEN** the user runs `docker run --rm ghcr.io/dirnei/map2plotter:1.1.0 python -c "import map2plotter; print(map2plotter.__version__)"`
- **THEN** it prints `1.1.0`
