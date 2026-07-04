# 🤺 Fencing Videos Downloader

**Découpez un extrait précis d'une vidéo YouTube ou d'un flux FencingTV, en quelques clics.**

Fencing Videos Downloader est une petite application de bureau (Windows, macOS, Linux)
qui permet de télécharger des portions de vidéos youtube ou FencingTV

## Téléchargement

Rendez-vous sur la page [Releases](../../releases/latest) et téléchargez le fichier
correspondant à votre système :

| Système                        | Fichier à télécharger                 |
| ------------------------------ | ------------------------------------- |
| Windows 10 / 11                | `FencingVideosDownloader-Windows.exe` |
| macOS (Apple Silicon, M1 et +) | `FencingVideosDownloader-macOS.zip`   |
| Linux                          | `FencingVideosDownloader-Linux`       |

> Les Mac Intel (avant 2021) ne sont pas couverts par les exécutables :
> sur ces machines, installez Python puis lancez l'application depuis les sources
> (`pip install .` puis `python -m fencing_videos_downloader`).

### Premier lancement

- **Windows** : SmartScreen peut afficher un avertissement (application non signée).
  Cliquez sur « Informations complémentaires » puis « Exécuter quand même ».
- **macOS** : décompressez le zip, puis **clic droit → Ouvrir** sur
  `FencingVideosDownloader.app` la première fois (application non signée).
- **Linux** : rendez le fichier exécutable puis lancez-le :

  ```bash
  chmod +x FencingVideosDownloader-Linux && ./FencingVideosDownloader-Linux
  ```

## Licence

[MIT](LICENSE)
