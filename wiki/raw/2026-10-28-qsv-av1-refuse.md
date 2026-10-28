# av1_qsv sur le portable — 2026-10-28

Rapporté par l'utilisateur. i5-1135G7, ffmpeg du PATH du portable (lancé
depuis C:\Users\Ummon, pas le dossier bin d'IRIS), PowerShell.

    ffmpeg.exe -v error -f lavfi -i nullsrc=s=256x144:d=0.05:r=25 -c:v av1_qsv -frames:v 1 -f null -
    [av1_qsv @ …] Current codec type is unsupported
    [av1_qsv @ …] some encoding parameters are not supported by the QSV runtime. Please double check the input parameters.
    … Error while opening encoder …
    … Task finished with error code: -40 (Function not implemented)
    AV1 8 bits  : code -40

Même résultat avec `-pix_fmt p010le` : « Current codec type is unsupported »,
code -40.
