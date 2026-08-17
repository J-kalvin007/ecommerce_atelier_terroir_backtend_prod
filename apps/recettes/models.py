import logging
import os
import shutil
import subprocess
import tempfile

from apps.core.models import BaseModel
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator
from django.db import models


logger = logging.getLogger(__name__)


# =====================================================
# CONSTANTES VIDÉO
# =====================================================

# Extensions brutes acceptées à l'upload (le fichier stocké final est
# toujours ré-encodé en .mp4 par la compression, quel que soit le format
# d'origine fourni par l'administrateur).
RECETTE_VIDEO_ALLOWED_EXTENSIONS = ["mp4", "mov", "avi", "mkv", "webm", "m4v"]

# Plafond de sécurité appliqué au fichier BRUT envoyé par l'admin, avant
# compression. Il ne s'agit pas de la contrainte métier (10 Mo) mais d'un
# garde-fou technique évitant qu'un fichier disproportionné ne bloque le
# serveur pendant l'appel ffmpeg synchrone déclenché dans Recette.save().
RECETTE_VIDEO_MAX_UPLOAD_SIZE_MB = 200

# Taille maximale imposée au fichier FINAL, une fois compressé. C'est la
# contrainte métier demandée : la vidéo stockée ne doit jamais dépasser 10 Mo.
RECETTE_VIDEO_MAX_FINAL_SIZE_MB = 10

RECETTE_VIDEO_MAX_UPLOAD_SIZE_BYTES = RECETTE_VIDEO_MAX_UPLOAD_SIZE_MB * 1024 * 1024
RECETTE_VIDEO_MAX_FINAL_SIZE_BYTES = RECETTE_VIDEO_MAX_FINAL_SIZE_MB * 1024 * 1024


def validate_recette_video_upload_size(file):
    """
    Valide la taille du fichier brut envoyé par l'administrateur, avant
    toute compression. Ce validateur est repris automatiquement par DRF
    (ModelSerializer copie les validators des champs de fichier du modèle).
    """
    if file.size > RECETTE_VIDEO_MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            f"La vidéo ne doit pas dépasser {RECETTE_VIDEO_MAX_UPLOAD_SIZE_MB} Mo "
            f"avant compression (fichier reçu : {file.size / (1024 * 1024):.1f} Mo)."
        )


def _probe_video_duration_seconds(input_path):
    """Interroge ffprobe pour obtenir la durée (en secondes) d'un fichier vidéo."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def _encode_video_to_target_size(input_path, output_path, target_size_bytes):
    """
    Ré-encode `input_path` en H.264/AAC (.mp4) vers `output_path`, en visant
    une taille finale proche de `target_size_bytes`.

    Méthode standard de compression "taille cible" : le bitrate vidéo est
    calculé à partir de la durée du média et de la taille voulue, avec une
    marge de sécurité de 3 % pour compenser l'overhead du conteneur MP4.
    """
    duration = _probe_video_duration_seconds(input_path)
    if duration <= 0:
        raise ValidationError("Impossible de déterminer la durée de la vidéo fournie.")

    audio_bitrate_bps = 128_000
    target_total_bitrate_bps = (target_size_bytes * 8 / duration) * 0.97
    video_bitrate_bps = max(int(target_total_bitrate_bps - audio_bitrate_bps), 100_000)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", str(video_bitrate_bps),
            "-maxrate", str(int(video_bitrate_bps * 1.2)),
            "-bufsize", str(int(video_bitrate_bps * 2)),
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ],
        capture_output=True,
        check=True,
        timeout=600,
    )


def _compress_recette_video(field_file):
    """
    Compresse le fichier vidéo brut porté par `field_file` (FieldFile pas
    encore écrit sur le storage) et retourne un ContentFile prêt à remplacer
    le contenu original avant sauvegarde.

    Lève ValidationError si ffmpeg est indisponible sur le serveur, si la
    compression échoue, ou si la taille finale dépasse malgré tout la limite
    autorisée.
    """
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise ValidationError(
            "La compression vidéo est indisponible : ffmpeg n'est pas installé sur le serveur."
        )

    original_name = field_file.name
    suffix = os.path.splitext(original_name)[1] or ".mp4"

    with tempfile.TemporaryDirectory(prefix="recette_video_") as tmp_dir:
        input_path = os.path.join(tmp_dir, f"input{suffix}")
        output_path = os.path.join(tmp_dir, "output.mp4")

        field_file.seek(0)
        with open(input_path, "wb") as tmp_input:
            for chunk in field_file.chunks():
                tmp_input.write(chunk)

        try:
            _encode_video_to_target_size(
                input_path,
                output_path,
                RECETTE_VIDEO_MAX_FINAL_SIZE_BYTES,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr
            logger.error("Échec de la compression ffmpeg pour %s : %s", original_name, stderr)
            raise ValidationError(
                "La compression de la vidéo a échoué. Vérifiez que le fichier n'est pas corrompu."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValidationError(
                "La compression de la vidéo a dépassé le délai autorisé."
            ) from exc

        final_size = os.path.getsize(output_path)
        if final_size > RECETTE_VIDEO_MAX_FINAL_SIZE_BYTES:
            raise ValidationError(
                f"Même après compression, la vidéo dépasse {RECETTE_VIDEO_MAX_FINAL_SIZE_MB} Mo "
                f"({final_size / (1024 * 1024):.1f} Mo). Fournissez une vidéo plus courte ou de "
                f"résolution plus faible."
            )

        with open(output_path, "rb") as compressed_file:
            compressed_bytes = compressed_file.read()

    base_name = os.path.splitext(os.path.basename(original_name))[0]
    logger.info(
        "Vidéo de recette compressée : %s -> %.1f Mo",
        original_name,
        len(compressed_bytes) / (1024 * 1024),
    )
    return ContentFile(compressed_bytes, name=f"{base_name}.mp4")


# =====================================================
# RECETTE
# =====================================================

class Recette(BaseModel):
    """
    Recette de cuisine associée à un produit ou à un pack de produits.

    Reproduit la logique éditoriale d'une page recette de site e-commerce
    (nom, description, ingrédients, instructions, vidéo et visuels), sur une
    table unique. Tous les champs sont nullable afin de permettre la
    création progressive d'une recette (brouillon) par l'administrateur.
    """

    nom = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nom de la recette",
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Description",
        help_text="Court résumé éditorial de la recette.",
    )

    ingredients = models.TextField(
        null=True,
        blank=True,
        verbose_name="Ingrédients",
        help_text="Liste des ingrédients de la recette (un par ligne).",
    )

    instructions = models.TextField(
        null=True,
        blank=True,
        verbose_name="Instructions",
        help_text="Étapes de préparation de la recette.",
    )

    video_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Lien vidéo externe",
        help_text="Lien vers une vidéo externe (YouTube, Vimeo, etc.).",
    )

    video = models.FileField(
        upload_to="recettes/videos/%Y/%m/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=RECETTE_VIDEO_ALLOWED_EXTENSIONS),
            validate_recette_video_upload_size,
        ],
        verbose_name="Vidéo hébergée",
        help_text=(
            "Vidéo de la recette uploadée directement. Compressée automatiquement "
            f"côté serveur pour ne jamais dépasser {RECETTE_VIDEO_MAX_FINAL_SIZE_MB} Mo."
        ),
    )

    image_1 = models.ImageField(
        upload_to="recettes/images/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Image 1",
    )

    image_2 = models.ImageField(
        upload_to="recettes/images/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Image 2",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="recettes",
        null=True,
        blank=True,
        verbose_name="Produit associé",
    )

    pack = models.ForeignKey(
        "promotions.Pack",
        on_delete=models.CASCADE,
        related_name="recettes",
        null=True,
        blank=True,
        verbose_name="Pack associé",
    )

    class Meta:
        db_table = "recettes_recettes"
        verbose_name = "Recette"
        verbose_name_plural = "Recettes"
        ordering = ["-created_at"]
        constraints = [
            # Une recette est liée à UN produit OU à UN pack, jamais aux deux
            # à la fois. Les deux champs restent individuellement nullable
            # (une recette "brouillon" peut n'avoir ni l'un ni l'autre).
            models.CheckConstraint(
                check=~(
                    models.Q(product__isnull=False)
                    & models.Q(pack__isnull=False)
                ),
                name="recette_produit_xor_pack",
                violation_error_message=(
                    "Une recette ne peut être liée qu'à un seul produit OU un "
                    "seul pack, jamais les deux à la fois."
                ),
            ),
        ]

    def __str__(self):
        return self.nom or str(self.id)

    def save(self, *args, **kwargs):
        """
        Compresse la vidéo côté serveur avant écriture, si un nouveau
        fichier vient d'être assigné au champ `video`.

        `_committed` vaut False tant que le FieldFile n'a pas encore été
        écrit sur le storage : c'est le signal fiable qu'il s'agit bien d'un
        nouvel upload (création ou remplacement), et non du fichier déjà
        stocké rechargé depuis la base lors d'une sauvegarde ne touchant pas
        la vidéo.
        """
        if self.video and not self.video._committed:
            self.video = _compress_recette_video(self.video)

        super().save(*args, **kwargs)
