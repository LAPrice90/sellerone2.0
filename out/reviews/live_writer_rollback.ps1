$manifest = Import-Csv -Path "out\reviews\live_writer_rollback_manifest.csv"
foreach($row in $manifest){
  if(Test-Path $row.source_live){
    $destDir = Split-Path -Parent $row.destination_legacy
    if(-not (Test-Path $destDir)){ New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Copy-Item -Path $row.source_live -Destination $row.destination_legacy -Force
  }
}
