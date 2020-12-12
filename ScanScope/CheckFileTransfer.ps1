[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$uri = "https://vpn-test.cptac.vai.org/ImportSlide"
ls *.svs | ForEach-Object -Parallel {
    $body = @{"filename" = $_.Name; "size" = $_.Length}
    $result = Invoke-RestMethod -Method 'POST' -Uri $uri -Body $body
    del $filename
} 
