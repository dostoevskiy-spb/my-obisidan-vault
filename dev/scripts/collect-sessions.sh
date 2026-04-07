#!/usr/bin/env bash
# collect-sessions.sh — Сбор логов сессий Claude Code из проектов в Obsidian vault
# Запускается по cron (02:00) или вручную
# Трекинг через пометки [imported:YYYY-MM-DD last-log:HH:MM] в SESSION_INDEX.md

set -euo pipefail

# === Конфигурация ===
VAULT_DIR="/home/pavel/dev/obsidian/dev"
SCAN_DIR="/home/pavel/dev/www"
RAW_DIR="${VAULT_DIR}/01 Inbox/sessions/raw"
LOCK_FILE="/tmp/vault-collect.lock"
LOG_FILE="/tmp/vault-collect.log"
TODAY=$(date +%Y-%m-%d)

# === Логирование ===
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# === Lock ===
if [ -f "$LOCK_FILE" ]; then
    # Проверяем не стал ли lock "протухшим" (> 1 часа)
    if [ "$(find "$LOCK_FILE" -mmin +60 2>/dev/null)" ]; then
        log "WARN: Стёрт протухший lock-файл"
        rm -f "$LOCK_FILE"
    else
        log "ERROR: Lock-файл существует, другой процесс работает"
        exit 1
    fi
fi
trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

log "=== Начало сбора сессий ==="

IMPORTED_COUNT=0
UPDATED_COUNT=0
SKIPPED_COUNT=0

# === Функции ===

# Извлечь имя проекта из пути
# /home/pavel/dev/www/bringo/bringo-co-uk/main → bringo
# /home/pavel/dev/www/omnicom/crm-v2 → omnicom-crm-v2
get_project_name() {
    local path="$1"
    local relative="${path#${SCAN_DIR}/}"
    # Берём значимые части пути, заменяем / на -
    echo "$relative" | sed 's|/main$||; s|/|-|g; s|-co-uk||g'
}

# Найти последний "### HH:MM" в файле сессии
get_last_log_time() {
    local file="$1"
    grep -oP '^### \K\d{2}:\d{2}' "$file" | tail -1
}

# Извлечь дату сессии из файла (строка **Дата:** YYYY-MM-DD HH:MM)
get_session_date() {
    local file="$1"
    grep -oP '^\*\*Дата:\*\* \K\d{4}-\d{2}-\d{2}' "$file" | head -1
}

# Создать frontmatter + скопировать содержимое файла в raw
copy_to_raw() {
    local src="$1"
    local dest="$2"
    local project="$3"
    local session_date="$4"
    local project_tag
    project_tag=$(echo "$project" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

    {
        echo "---"
        echo "type: session-log-raw"
        echo "project: ${project}"
        echo "source: ${src}"
        echo "session_date: ${session_date}"
        echo "tags: [session-log, raw, ${project_tag}]"
        echo "created: ${TODAY}"
        echo "status: unprocessed"
        echo "---"
        echo ""
        cat "$src"
    } > "$dest"
}

# Обработать SESSION_INDEX.md проекта
process_session_index() {
    local project_dir="$1"
    local sessions_dir="${project_dir}/.claude/sessions"
    local index_file="${sessions_dir}/SESSION_INDEX.md"
    local project_name
    project_name=$(get_project_name "$project_dir")

    if [ ! -f "$index_file" ]; then
        log "  Нет SESSION_INDEX.md в ${sessions_dir}"
        return
    fi

    local index_modified=false
    local tmp_index
    tmp_index=$(mktemp)
    cp "$index_file" "$tmp_index"

    # Собираем файлы уже учтённые в индексе
    local indexed_files=()

    while IFS= read -r line; do
        # Пропускаем заголовки и пустые строки
        if [[ "$line" != -\ * ]]; then
            echo "$line" >> "${tmp_index}.new"
            continue
        fi

        # Извлечь имя файла из markdown-ссылки: [text](filename.md)
        local filename
        filename=$(echo "$line" | grep -oP '\]\(\K[^)]+\.md' || true)
        if [ -z "$filename" ]; then
            echo "$line" >> "${tmp_index}.new"
            continue
        fi

        indexed_files+=("$filename")
        local src_file="${sessions_dir}/${filename}"

        if [ ! -f "$src_file" ]; then
            echo "$line" >> "${tmp_index}.new"
            continue
        fi

        local dest_file="${RAW_DIR}/${project_name}--${filename}"
        local last_log
        last_log=$(get_last_log_time "$src_file")
        local session_date
        session_date=$(get_session_date "$src_file")
        [ -z "$session_date" ] && session_date="$TODAY"

        # Проверяем: есть ли уже метка [imported:...]?
        if echo "$line" | grep -q '\[imported:'; then
            # Уже импортирован — проверяем обновления
            local old_last_log
            old_last_log=$(echo "$line" | grep -oP 'last-log:\K\d{2}:\d{2}' || true)

            if [ -n "$last_log" ] && [ -n "$old_last_log" ] && [ "$last_log" != "$old_last_log" ]; then
                # Сессия обновилась — ре-импорт
                log "  ОБНОВЛЕНО: ${filename} (${old_last_log} → ${last_log})"
                copy_to_raw "$src_file" "$dest_file" "$project_name" "$session_date"
                # Обновляем метку
                local new_line
                new_line=$(echo "$line" | sed "s/\[imported:[^ ]* last-log:[0-9:]*\]/[imported:${TODAY} last-log:${last_log}]/")
                echo "$new_line" >> "${tmp_index}.new"
                index_modified=true
                UPDATED_COUNT=$((UPDATED_COUNT + 1))
            else
                # Не изменилась — пропускаем
                echo "$line" >> "${tmp_index}.new"
                SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            fi
        else
            # Новая запись — импортируем
            log "  ИМПОРТ: ${filename}"
            copy_to_raw "$src_file" "$dest_file" "$project_name" "$session_date"
            # Добавляем метку
            [ -z "$last_log" ] && last_log="00:00"
            echo "${line} [imported:${TODAY} last-log:${last_log}]" >> "${tmp_index}.new"
            index_modified=true
            IMPORTED_COUNT=$((IMPORTED_COUNT + 1))
        fi
    done < "$tmp_index"

    # Ищем "осиротевшие" файлы — есть на диске, но нет в индексе
    for src_file in "${sessions_dir}"/*.md; do
        [ ! -f "$src_file" ] && continue
        local base
        base=$(basename "$src_file")
        [ "$base" = "SESSION_INDEX.md" ] && continue

        local is_indexed=false
        for indexed in "${indexed_files[@]+"${indexed_files[@]}"}"; do
            if [ "$indexed" = "$base" ]; then
                is_indexed=true
                break
            fi
        done

        if [ "$is_indexed" = false ]; then
            local dest_file="${RAW_DIR}/${project_name}--${base}"
            if [ ! -f "$dest_file" ]; then
                local session_date
                session_date=$(get_session_date "$src_file")
                [ -z "$session_date" ] && session_date="$TODAY"
                local last_log
                last_log=$(get_last_log_time "$src_file")
                [ -z "$last_log" ] && last_log="00:00"

                log "  ИМПОРТ (orphan): ${base}"
                copy_to_raw "$src_file" "$dest_file" "$project_name" "$session_date"

                # Добавляем в индекс
                local title
                title=$(head -1 "$src_file" | sed 's/^# Сессия: //' | sed 's/^# //')
                echo "- [${session_date} — ${title}](${base}) — imported from orphan [imported:${TODAY} last-log:${last_log}]" >> "${tmp_index}.new"
                index_modified=true
                IMPORTED_COUNT=$((IMPORTED_COUNT + 1))
            fi
        fi
    done

    # Обновляем SESSION_INDEX.md если были изменения
    if [ "$index_modified" = true ] && [ -f "${tmp_index}.new" ]; then
        cp "${tmp_index}.new" "$index_file"
        # Коммитим в репозиторий проекта
        (cd "$project_dir" && git add ".claude/sessions/SESSION_INDEX.md" && \
         git commit -m "collect-sessions: updated import markers in SESSION_INDEX.md" 2>/dev/null) || true
        log "  SESSION_INDEX.md обновлён и закоммичен"
    fi

    rm -f "$tmp_index" "${tmp_index}.new"
}

# Обработать планы проекта (по mtime, без индекса)
process_plans() {
    local project_dir="$1"
    local project_name
    project_name=$(get_project_name "$project_dir")

    # .claude/sessions/plans/
    local plans_dir="${project_dir}/.claude/sessions/plans"
    if [ -d "$plans_dir" ]; then
        for plan_file in "${plans_dir}"/*.md; do
            [ ! -f "$plan_file" ] && continue
            local base
            base=$(basename "$plan_file")
            local dest_file="${RAW_DIR}/${project_name}--plan--${base}"
            if [ ! -f "$dest_file" ]; then
                log "  ИМПОРТ ПЛАН: ${base}"
                {
                    echo "---"
                    echo "type: session-plan-raw"
                    echo "project: ${project_name}"
                    echo "source: ${plan_file}"
                    echo "tags: [session-plan, raw, $(echo "$project_name" | tr '[:upper:]' '[:lower:]')]"
                    echo "created: ${TODAY}"
                    echo "status: unprocessed"
                    echo "---"
                    echo ""
                    cat "$plan_file"
                } > "$dest_file"
                IMPORTED_COUNT=$((IMPORTED_COUNT + 1))
            fi
        done
    fi

    # .claude/plans/ (глобальные планы проекта)
    local gplans_dir="${project_dir}/.claude/plans"
    if [ -d "$gplans_dir" ]; then
        for plan_file in "${gplans_dir}"/*.md; do
            [ ! -f "$plan_file" ] && continue
            local base
            base=$(basename "$plan_file")
            local dest_file="${RAW_DIR}/${project_name}--gplan--${base}"
            if [ ! -f "$dest_file" ]; then
                log "  ИМПОРТ GPLAN: ${base}"
                {
                    echo "---"
                    echo "type: session-plan-raw"
                    echo "project: ${project_name}"
                    echo "source: ${plan_file}"
                    echo "tags: [session-plan, raw, $(echo "$project_name" | tr '[:upper:]' '[:lower:]')]"
                    echo "created: ${TODAY}"
                    echo "status: unprocessed"
                    echo "---"
                    echo ""
                    cat "$plan_file"
                } > "$dest_file"
                IMPORTED_COUNT=$((IMPORTED_COUNT + 1))
            fi
        done
    fi
}

# === Основной цикл ===

# Рекурсивно ищем проекты с .claude/sessions/
while IFS= read -r sessions_dir; do
    project_dir=$(dirname "$(dirname "$sessions_dir")")
    log "Проект: ${project_dir}"
    process_session_index "$project_dir"
    process_plans "$project_dir"
done < <(find "$SCAN_DIR" -maxdepth 6 -type d -name "sessions" -path "*/.claude/sessions" 2>/dev/null)

# === Git: push изменения в vault ===
if [ $IMPORTED_COUNT -gt 0 ] || [ $UPDATED_COUNT -gt 0 ]; then
    log "Коммит в vault: ${IMPORTED_COUNT} новых, ${UPDATED_COUNT} обновлено"
    cd "$VAULT_DIR"
    git pull --rebase origin main 2>/dev/null || git pull origin main
    git add "01 Inbox/sessions/raw/"
    git commit -m "collect-sessions: ${IMPORTED_COUNT} imported, ${UPDATED_COUNT} updated [${TODAY}]" 2>/dev/null || true
    git push origin main 2>/dev/null || log "WARN: git push failed, будет подхвачено obsidian-git"
else
    log "Нечего импортировать"
fi

log "=== Итого: импортировано=${IMPORTED_COUNT}, обновлено=${UPDATED_COUNT}, пропущено=${SKIPPED_COUNT} ==="
log "=== Сбор завершён ==="
