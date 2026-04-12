function mmv
    mkdir -p (dirname $argv[2])
    mv $argv[1] $argv[2]
end
