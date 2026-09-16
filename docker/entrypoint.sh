#!/bin/sh
# ---------------------------------------------------------------------
# docker/entrypoint.sh — ilovani `appuser` (uid 10001) nomidan ishga tushiradi.
#
# Nima uchun bu kerak: konteyner root bilan boshlanadi, chunki named
# volume'lar (pdf_data, debug_data, temp_uploads) Docker tomonidan root
# egaligida yaratiladi. Agar image'da to'g'ridan-to'g'ri `USER appuser`
# yozilsa, mavjud volume'larga yozib bo'lmay ilova ishga tushmasdan
# yiqilardi ("PermissionError: /data/pdfs").
#
# Shu sababli: root bilan kirib egalikni bir marta to'g'rilaymiz va
# darhol huquqlarni tushiramiz. Ilova jarayoni HECH QACHON root emas.
#
# `chown -R` faqat egasi noto'g'ri bo'lgandagina bajariladi — aks holda
# minglab PDF ustidan har ishga tushishda yurish sekinlik qilardi.
# ---------------------------------------------------------------------
set -e

APP_UID=10001
APP_USER=appuser

if [ "$(id -u)" = "0" ]; then
    for dir in /data/pdfs /data/debug /tmp/omr_uploads; do
        [ -d "$dir" ] || mkdir -p "$dir"
        if [ "$(stat -c %u "$dir")" != "$APP_UID" ]; then
            echo "entrypoint: $dir egaligi to'g'rilanmoqda -> $APP_USER" >&2
            chown -R "$APP_USER:$APP_USER" "$dir"
        fi
    done
    exec gosu "$APP_USER" "$@"
fi

# Allaqachon root emas (masalan compose'da `user:` berilgan) — to'g'ridan
# to'g'ri ishga tushiramiz.
exec "$@"
