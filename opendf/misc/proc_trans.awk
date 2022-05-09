BEGIN {
	i=0;
}
{
	if (i==0 && substr($1, 1, 3)!="===") {
		printf("lost sync!\n%s\n", $0);
	}
	if (i==1) {
		did = $2;
	}
	if (i==2) {
		tid = $2;
	}
	if (i==5) {
		corr = $2;
	}
	if (i==7) {
		hyp = "";
		for (j=2; j<=NF; j++) hyp = hyp  " "  $j;
	}
	i = (i+1)%8;
	if (i==0) {
		printf("%s@@@%s@@@%s@@@%s\n", did, tid, corr, hyp);
	}
}


# use this script to process the results of the machine translation of the user requests (using the
#    MT train and eval pipeline used in the SMCalFlow paper/github), so we can inspect them
#    with show_simplification.py
# to run:
# awk -f proc_trans.awk valid.prediction_report.txt > transl.valid



