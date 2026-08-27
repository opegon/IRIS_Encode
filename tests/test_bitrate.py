"""
tests/test_bitrate.py — Le débit comparé au seuil est celui de la vidéo.

Un profil fixe un débit **vidéo** cible, et c'est un débit vidéo que reçoit
l'encodeur. Comparer le débit du conteneur — vidéo, audio et sous-titres
confondus — fausse la décision dans le sens du réencodage, d'autant plus que
les pistes audio sont grosses : sur un film porteur d'un TrueHD, l'écart
dépasse 40 %.
"""
from __future__ import annotations

from core.scanner import _video_bitrate


def _vid(bit_rate=None, bps=None) -> dict:
    s = {"codec_type": "video"}
    if bit_rate is not None:
        s["bit_rate"] = str(bit_rate)
    if bps is not None:
        s["tags"] = {"BPS": str(bps)}
    return s


def _audio(bit_rate=None, bps=None, **tags) -> dict:
    s = {"codec_type": "audio"}
    if bit_rate is not None:
        s["bit_rate"] = str(bit_rate)
    t = {k.upper(): str(v) for k, v in tags.items()}
    if bps is not None:
        t["BPS"] = str(bps)
    if t:
        s["tags"] = t
    return s


# ─── Sources du débit, dans l'ordre ───────────────────────────────────────────

def test_le_bit_rate_du_flux_prime():
    vid = _vid(bit_rate=5_000_000, bps=9_999_999)
    assert _video_bitrate(vid, [vid], {"bit_rate": "12000000"}) == 5_000_000


def test_le_tag_bps_prend_le_relais():
    """Un flux vidéo Matroska n'annonce presque jamais de bit_rate ; mkvmerge
    pose en revanche un tag BPS exact."""
    vid = _vid(bps=5_364_447)
    assert _video_bitrate(vid, [vid], {"bit_rate": "9611230"}) == 5_364_447


def test_a_defaut_le_conteneur_moins_les_autres_pistes():
    """Le cas de « The Zookeeper's Wife » : aucun tag BPS, mais les pistes
    audio déclarent leur débit."""
    vid = _vid()
    streams = [vid, _audio(bit_rate=384_000), _audio(bit_rate=1_536_000)]
    assert _video_bitrate(vid, streams, {"bit_rate": "11528127"}) == 9_608_127


def test_les_tags_des_pistes_audio_servent_a_la_soustraction():
    vid = _vid()
    streams = [vid, _audio(bps=640_000), _audio(bps=3_501_887)]
    assert _video_bitrate(vid, streams, {"bit_rate": "9611230"}) == 5_469_343


def test_un_debit_de_piste_inconnu_ne_retire_rien():
    """Prudence : sans le débit d'une piste, mieux vaut surestimer la vidéo et
    réencoder que sous-estimer et laisser passer un fichier trop gros."""
    vid = _vid()
    streams = [vid, _audio()]
    assert _video_bitrate(vid, streams, {"bit_rate": "9000000"}) == 9_000_000


def test_soustraction_absurde_ecartee():
    """Des tags incohérents ne doivent pas produire un débit négatif ou nul."""
    vid = _vid()
    streams = [vid, _audio(bps=20_000_000)]
    assert _video_bitrate(vid, streams, {"bit_rate": "9000000"}) == 9_000_000


def test_rien_de_lisible():
    vid = _vid()
    assert _video_bitrate(vid, [vid], {}) == 0


def test_une_seconde_piste_video_ne_se_soustrait_pas():
    """Une pochette embarquée est un flux vidéo : la soustraire n'aurait
    aucun sens, et son débit déclaré est fantaisiste."""
    vid   = _vid()
    cover = {"codec_type": "video", "bit_rate": "8000000"}
    streams = [vid, cover, _audio(bps=640_000)]
    assert _video_bitrate(vid, streams, {"bit_rate": "9000000"}) == 8_360_000


# ─── Effet sur la décision ────────────────────────────────────────────────────

def test_un_film_sous_le_seuil_n_est_plus_reencode(tmp_path):
    """Watchmen : 9 611k dans le conteneur, dont 4 141k d'audio. Face à un
    seuil 4K de 8 000k, le total déclenchait un réencodage que le débit vidéo
    réel — 5 364k — ne justifie pas."""
    from core.decision import VideoAction, decide
    from core.profiles import Profile
    from core.scanner import AudioTrack, VideoInfo

    p = tmp_path / "film.mkv"
    p.write_bytes(b"")
    info = VideoInfo(
        path=p, width=3840, height=1596, bitrate=5_364_447, codec="hevc",
        duration=12923.0, frame_count=0, dv_profile=None,
        audio_tracks=[
            AudioTrack(index=0, codec="ac3", channels=6, language="fre",
                       title="", bitrate=640_000),
            AudioTrack(index=1, codec="truehd", channels=6, language="eng",
                       title="", bitrate=3_501_887),
        ],
    )
    prof = Profile(id="t", data={"bitrate_4k_kbps": 8000, "keep_4k": True,
                                 "bitrate_1080p_kbps": 5000,
                                 "bitrate_720p_kbps": 2000})
    assert decide(info, prof).video.action == VideoAction.SKIP
