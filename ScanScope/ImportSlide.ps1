param($Hostname)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
ls *.svs | ForEach-Object -Parallel {
    If (((Get-Date) - $_.LastWriteTime).TotalSeconds -lt 30) {return}
    $body = ConvertTo-Json @{"filename" = $_.Name; "size" = $_.Length}
    $result = Invoke-RestMethod -Method 'POST' -Uri "https://${using:Hostname}/ImportSlide" -Body $body
    Remove-Item $result.filename
} 
