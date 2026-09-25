# Proposal

## Why

map2plotter is now its own project, but it has no releases. The version in `pyproject.toml` (0.2.0) is stale and no longer matches the CHANGELOG, whose last upstream entry is 0.3.0. There are no git tags. The Docker workflow publishes `latest` on every push to `main`, so an image is never tied to a version and `latest` can contain unfinished work. The commit messages already follow Conventional Commits (`feat:`, `refactor:`, `docs:`), so release-please can derive versions and release notes from them without changing how you work.

## What Changes

- **Release automation:** release-please runs on every push to `main` and keeps a release pull request open. That PR bumps the version in `pyproject.toml`, updates `CHANGELOG.md` and updates the release manifest. Merging it creates the git tag `vX.Y.Z` and a GitHub release with the generated notes.
- **First release is 1.0.0.** After that, versions follow Conventional Commits: `fix:` bumps the patch, `feat:` the minor, and a breaking change (`!`) the major. Release notes for 1.0.0 cover the map2plotter commits since the fork from maptoposter.
- **BREAKING (Docker tags):**
  - The GHCR image is only pushed when a release is created, tagged `X.Y.Z`, `X.Y`, `X` and `latest`.
  - Pushes to `main` and tag pushes no longer publish an image, and the `<commit-sha>` / `<branch>` tags stop.
- **Version everywhere from one place:** the release PR's version is what `map2plotter.__version__`, the User-Agent and the image tags report. The image also carries OCI labels for version, source and license.
- **CHANGELOG:** the hand-written "Unreleased" section is kept as the detailed notes for the changes since maptoposter 0.3.0, under a heading that fits below the generated 1.0.0 entry. Release-please owns everything above it from now on.
- **Not in this change:** publishing to PyPI, signing images, multi-arch images, and changing the PR checks.

## Capabilities

### New Capabilities
- `release-publishing`: covers how versions and releases are created from commits, how the changelog and package version are kept in sync, and which Docker images are published to GHCR, and when.

### Modified Capabilities
<!-- None: the container's runtime behaviour ("Container hosts the web interface") is unchanged; only when and under which tags the image is published changes, which the new capability covers. -->

## Impact

- **New files:** `release-please-config.json`, `.release-please-manifest.json`, and a `release.yml` workflow that combines release-please with the image build.
- **Removed:** `.github/workflows/docker-publish.yml`, since its job moves into the release workflow.
- **Changed:**
  - `pyproject.toml` (the version is managed by release-please)
  - `CHANGELOG.md` (its intro and the heading of the hand-written section)
  - README (releases, image tags, and how to write commit messages)

  The Dockerfile is unchanged: the OCI labels are added by the image build step.
- **Repository settings (manual, one-time):**
  - Actions need "Read and write permissions" and "Allow GitHub Actions to create and approve pull requests", so release-please can open its PR.
  - After the first push, the GHCR package's visibility has to be set to public.
- **Users:** anyone pulling `ghcr.io/dirnei/map2plotter:latest` now gets the newest release instead of the newest `main`. Pinned `:<sha>` tags from earlier builds are no longer produced.
