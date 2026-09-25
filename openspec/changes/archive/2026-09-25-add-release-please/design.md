# Design

## Context

- `.github/workflows/docker-publish.yml` builds on pushes to `main`/`master` and on `v*.*.*` tags. It pushes `latest`, `<sha>` and `<ref_name>` to a lowercased `ghcr.io/<repository>`, using `GITHUB_TOKEN` with `packages: write`.
- `pr-checks.yml` runs on `pull_request` only.
- There are no git tags. `pyproject.toml` has `version = "0.2.0"`, while the CHANGELOG's last upstream release is 0.3.0.
- `map2plotter.__version__` is read from the package metadata, which comes from `pyproject.toml`. The User-Agent is built from it. The Docker image installs the package with `pip install --no-deps .`, so the image reports whatever version `pyproject.toml` has at build time.
- The CHANGELOG follows Keep a Changelog. Its top section is `## [Unreleased] - Community Contributions`, hand-written notes for everything since upstream 0.3.0, followed by the upstream 0.3.0 … 0.1.0 entries.
- The map2plotter work starts after commit `41c5244` ("feat: docker setup for the project", the base of the fork). The seven commits after it are all Conventional Commits.
- Commit messages are one-line subjects only, never bodies or footers.

## Goals / Non-Goals

**Goals:**
- One workflow in which the release and the image publish cannot drift apart.
- The version lives in exactly one file (`pyproject.toml`), written by release-please.

**Non-Goals:**
- PyPI publishing, multi-arch (arm64) images, image signing or SBOMs.
- Enforcing Conventional Commits on pull requests (for example with a commitlint check).

## Decisions

### 1. release-please in manifest mode, `python` release type
`release-please-config.json`:
```json
{
  "packages": {
    ".": {
      "release-type": "python",
      "package-name": "map2plotter",
      "include-component-in-tag": false,
      "changelog-path": "CHANGELOG.md",
      "release-as": "1.0.0"
    }
  },
  "bootstrap-sha": "41c5244",
  "changelog-sections": [
    {"type": "feat", "section": "Features"},
    {"type": "fix", "section": "Bug Fixes"},
    {"type": "perf", "section": "Performance Improvements"},
    {"type": "refactor", "section": "Code Refactoring"},
    {"type": "revert", "section": "Reverts"},
    {"type": "docs", "section": "Documentation", "hidden": true},
    {"type": "test", "section": "Tests", "hidden": true},
    {"type": "ci", "section": "Continuous Integration", "hidden": true},
    {"type": "chore", "section": "Miscellaneous", "hidden": true}
  ]
}
```
`.release-please-manifest.json` starts at `{".": "0.3.0"}`, the last released version of the code base.

- `python` updates `version` in `pyproject.toml`. `__init__.py` has no literal version, so there is nothing else to update.
- `include-component-in-tag: false` gives plain `v1.0.0` tags.
- `refactor` is visible because the two BREAKING changes so far (the package layout and the rename) are `refactor:` commits. Without it, the 1.0.0 notes would not mention them.

*Alternative:* the `simple` type with `extra-files` for `pyproject.toml`. That is more configuration for the same result.

### 2. Starting at 1.0.0 with `release-as`, then removing it
The usual way to force a version is a `Release-As: 1.0.0` commit footer, but footers are not used in this repository. `release-as` in the config does the same thing. It has to be removed right after 1.0.0 is released, or every later release PR would propose 1.0.0 again. That removal is its own task, with its own commit.

`bootstrap-sha: 41c5244` limits the first scan to the map2plotter commits. The generated 1.0.0 notes therefore list the fork's work, not upstream's history. release-please ignores `bootstrap-sha` once a release exists.

### 3. One workflow, release job then image job
`.github/workflows/release.yml`, on `push` to `main`:
- **Job `release-please`:** runs `googleapis/release-please-action@v4` with `GITHUB_TOKEN`, with permissions `contents: write` and `pull-requests: write`. It exposes the outputs `release_created`, `tag_name` and `sha`.
- **Job `docker`:** `needs: release-please`, `if: needs.release-please.outputs.release_created == 'true'`, permissions `contents: read` and `packages: write`.
  - It checks out `needs.release-please.outputs.sha`, logs in to GHCR and sets up Buildx.
  - `docker/metadata-action@v5` produces the tags and labels:
    - images `ghcr.io/${{ github.repository }}` (metadata-action lowercases it)
    - `type=semver,pattern={{version}}` / `{{major}}.{{minor}}` / `{{major}}`, with `value=${{ needs.release-please.outputs.tag_name }}`
    - `type=raw,value=latest`
    - an explicit `org.opencontainers.image.licenses=MIT` label
  - `docker/build-push-action@v6` pushes them.

Why one workflow: a release created with `GITHUB_TOKEN` does not trigger other workflows (no `release: published` or `push: tags` run), so a separate "on release" workflow would never start. Gating a second job on the first one's output avoids needing a personal access token.

`docker-publish.yml` is deleted.

*Alternatives:*
- A personal access token or GitHub App token for release-please, plus a separate `on: release` workflow. This decouples the two, but adds a secret to manage.
- Keep `docker-publish.yml` for pushes to `main`. That was rejected: you chose image pushes on releases only.

### 4. The labels come from metadata-action, not the Dockerfile
metadata-action already emits `org.opencontainers.image.version`, `.source`, `.revision` and `.created` from the release context, and the licenses label is set explicitly. Hard-coding `LABEL`s in the Dockerfile would duplicate this and go stale for local builds. The Dockerfile stays unchanged.

### 5. CHANGELOG handover
- The intro changes to say the entries from 1.0.0 on are generated by release-please from Conventional Commits.
- `## [Unreleased] - Community Contributions` becomes `## Changes since maptoposter 0.3.0 (detailed notes for 1.0.0)`. release-please inserts each new entry above the first existing `##` heading, so the generated 1.0.0 entry lands directly above these detailed notes, followed by the upstream releases.

### 6. The README documents the flow
A short "Releases" section covers:
- the commit-type-to-version table
- that merging the release PR publishes the release and the image
- the image tags (`X.Y.Z`, `X.Y`, `X`, `latest`)

The Docker examples keep using `:latest`, and one pinned example is added (`:1`).

## Risks / Trade-offs

- [The release PR is opened with `GITHUB_TOKEN`, so `pr-checks.yml` does not run on it] → It changes only the version, the changelog and the manifest. The code it releases was already checked on its own pull requests. A PAT can be added later if checks on the release PR are wanted.
- [`release-as` is forgotten after 1.0.0] → A dedicated task removes it right after the first release. The next release PR (for example 1.0.1) shows immediately whether it is gone.
- [`bootstrap-sha` in the wrong place pulls in upstream commits, or misses fork commits] → The release PR is a draft of the notes. Check its changelog before merging, and correct the sha if needed. Nothing is released until the merge.
- [The workflow can only really be tested on GitHub] → Locally, lint it with actionlint (Docker image `rhysd/actionlint`) and validate the JSON configs. The first real run happens on the first push to `main`, which only opens a PR and cannot publish anything by itself.
- [A repository setting blocks Actions from creating PRs, so the release job fails with 403] → Setting "Allow GitHub Actions to create and approve pull requests" and "Read and write permissions" is listed as a manual step.

## Migration Plan

1. Merge to `main`. The workflow opens the release PR "chore(main): release 1.0.0".
2. Review the PR's CHANGELOG and version, then merge it. This creates the tag `v1.0.0`, the GitHub release, and the image `ghcr.io/dirnei/map2plotter:1.0.0` / `1.0` / `1` / `latest`.
3. Remove `release-as` from the config (`chore: stop forcing release version`).
4. Set the GHCR package to public.

Rollback: revert the commit. Tags and releases that were already created stay, and can be deleted by hand.
