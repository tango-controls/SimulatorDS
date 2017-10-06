

# The "other" image uses 6GB
# 

cd /home/ubuntu
mkdir src
mkdir bin
mkdir ds
mkdir site-packages

cd src 
git clone https://github.com/tango-controls/fandango fandango.git
git clone https://github.com/tango-controls/panic panic.git
git clone https://github.com/tango-controls/simulatords simulatords.git

cd /home/ubuntu/site-packages
LNAME=fandango
ln -s /home/ubuntu/$LNAME.git/$LNAME
cd $LNAME
git checkout develop

cd /home/ubuntu/site-packages
LNAME=panic
ln -s /home/ubuntu/$LNAME.git/$LNAME
cd $LNAME
git checkout develop

cd /home/ubuntu/site-packages
LNAME=simulatords
ln -s /home/ubuntu/$LNAME.git/$LNAME

cd /home/ubuntu/ds
ln -s /home/ubuntu/site-packages/simulatords/SimulatorDS.py
