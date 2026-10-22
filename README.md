# Курсы валют · Калининград
1. Создайте репозиторий на GitHub, загрузите все файлы (включая папку .github).
2. Settings → Pages → Deploy from branch → main / root.
3. Settings → Actions → General → Workflow permissions → Read and write.
4. Actions → update-rates → Run workflow. Дальше обновление каждые 30 минут автоматически.
Сайт: https://ВАШ_ЛОГИН.github.io/РЕПОЗИТОРИЙ/
Парсер банков (scraper/fetch_rates.py, функция banki) — best effort: после первого запуска проверьте лог и data/rates.json.
