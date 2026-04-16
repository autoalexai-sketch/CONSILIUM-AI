# copy_frontend.ps1 - копирует фронтенд из Consilium AI в v30
$src = "C:\Users\HP\OneDrive\Рабочий стол\Consilium AI\frontend"
$dst = "C:\Users\HP\OneDrive\Рабочий стол\Consilium AI v30\frontend"

Remove-Item "$dst\js\app_chunk0.js" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$dst\js" | Out-Null
New-Item -ItemType Directory -Force -Path "$dst\css" | Out-Null

Copy-Item "$src\js\app.js" "$dst\js\app.js" -Force
Write-Host "OK app.js" -ForegroundColor Green

Copy-Item "$src\css\styles.css" "$dst\css\styles.css" -Force
Write-Host "OK styles.css" -ForegroundColor Green

$html = Get-Content "$src\index.html" -Raw -Encoding UTF8
$html = $html -replace 'href="frontend/css/', 'href="css/'
$html = $html -replace 'src="frontend/js/', 'src="js/'
Set-Content "$dst\index.html" $html -Encoding UTF8
Write-Host "OK index.html (пути исправлены)" -ForegroundColor Green

Write-Host "Готово! Открой http://localhost:8000" -ForegroundColor Cyan
