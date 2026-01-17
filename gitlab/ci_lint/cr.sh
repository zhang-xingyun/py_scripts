#!/bin/bash
## */5 * * * * /home/david/bin/set_cr_lst.sh >> /home/david/data/cr_update.log   2>&1
echo "------------start run the update hooks"-----------------
echo `date`
stamp=$(date +%Y%m%d%H%M%S)
echo "--------------------------------------------------------"

new_lst="/home/david/data/cr.lst"
old_lst="/home/david/data/cr.pre"
/home/david/bin/get_cr.py   > ${new_lst}.src

sort -u ${new_lst}.src > ${new_lst}

run_script=1

if [ -e $old_lst ]; then
    comm -13  ${old_lst} ${new_lst} >  ${new_lst}.delta
    new_lines=$(wc -l ${new_lst}.delta | cut -d " " -f1)
    if [ $new_lines -gt 0 ]; then
        run_script=1
        cp ${old_lst} ${old_lst}-${stamp}
    else
        run_script=0
    fi        
fi

if [ $run_script -gt 0 ]; then  
    ##
    echo "copy delta list to remote host"
    scp ${new_lst}.delta peng05.li@10.10.100.3:/home/users/peng05.li/custom_hooks/cr.lst
    echo "add hook at remote host"
    ssh peng05.li@10.10.100.3  /home/users/peng05.li/custom_hooks/batch_update_hooks.sh
    ##
    cp -f ${new_lst}.delta  ${new_lst}.delta-${stamp}
    cp -f ${new_lst} ${old_lst}
else
    echo "no new repo add, skip run ..."  
    cat ${new_lst}.delta
fi

