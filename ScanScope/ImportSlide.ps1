param($Hostname)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
ls *.svs | ForEach-Object -Parallel {
    # Don't start before Scanner is done writing (>2 minutes old?), and give up after file is 22 minutes old
    $age = ((Get-Date) - $_.LastWriteTime).TotalMinutes
    If (($age -lt 2) -or ($age -gt 22)) {return}
    $body = ConvertTo-Json @{"filename" = $_.Name; "size" = $_.Length}
    $result = Invoke-RestMethod -Method 'POST' -Uri "https://${using:Hostname}/ImportSlide" -Body $body
    Remove-Item $result.filename
} 
