param($Hostname)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
ls *.svs | ForEach-Object -Parallel {
    $body = ConvertTo-Json @{"filename" = $_.Name; "size" = $_.Length}
    $result = Invoke-RestMethod -Method 'POST' -Uri "https://${using:Hostname}/ImportSlide" -Body $body
    del $result.filename
} 
