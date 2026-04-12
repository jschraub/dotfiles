function mcp
    mkdir -p (dirname $argv[2])
    cp $argv[1] $argv[2]
end
