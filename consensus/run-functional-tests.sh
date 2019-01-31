if [ -z ${PYTHONPATH} ]; then
    echo Must set PYTHONPATH to the zeus location;
    exit;
fi

cd "$(dirname "$0")"
TOP_DIR=$(pwd)

for dir in $(ls tests)
do
    cd tests/${dir} && ./run.sh && cd ${TOP_DIR}
done
