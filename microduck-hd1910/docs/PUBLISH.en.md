[简体中文](PUBLISH.md) | **English** | [Русский](PUBLISH.ru.md)

# Publishing this repository

Project: [kissqy / Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy). Open the **whole repository folder containing the root README.md, microduck-hd 1910, and release-assets** in VS Code.

## Published content

- `public-image-r1` Release: `microduck-zero3w-0.15.1-R1.img.xz` public system image.
- Root `release-assets/`: `Microduck-Console-R17-V167.zip` and `Microduck-Training-Studio-R1.5.27.zip`.
- `microduck-hd1910/firmware/`: control.43 source; `console/` contains V167 console source.
- `microduck-hd1910/training-console/`: R1.5.27 source.

The homepage ZIP links download repository files directly and do not depend on separate Release attachments. Current source lives on `main`; the old image tag's automatic Source code attachments do not follow updates to `main`.

## Future synchronization

With no uncommitted local changes, pull the remote first, then replace the programs and source that need updating:

```powershell
git pull --ff-only
git status -sb
```

In VS Code Source Control, **stage → enter a commit message → commit → push**. Staging or committing locally does not update GitHub; the remote changes only after a successful push. If changes are pending, commit or safely save them before pulling. Do not discard them or force-push.

Check homepage download names, firmware BUILD, source, and runtime ZIPs together when updating. Preserve the existing component LICENSE; do not choose a new MIT or Apache license to replace this repository's licensing.

New runtime packages can go in `release-assets/` or in **Releases → Edit release → Attachments**. Large system images are distributed through Releases. A release tag identifies one commit; do not move old tags to replace their source.
