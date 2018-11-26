#include "rdma_cs.h"
#include <sys/time.h>
#include <stdio.h>
#include <pthread.h>

long REGION_LENGTH = 0;
long lifetime = 0;
uint8_t opcode;
long totalDelay=0;
int connect_four(struct rdma_cm_id *, struct rdma_event_channel *, char *, short int);
char *fileaddr;
long getMicrotime(){
	struct timeval currentTime;
	gettimeofday(&currentTime, NULL);
	return currentTime.tv_sec * (int)1e6 + currentTime.tv_usec;
}

void* cpu(void* args)
{

	long double a[4], b[4] , loadavg;
	FILE *fp;
	int cnt = 0 ;
	long simulationStartTime=getMicrotime();
	while (1)
	{
		if(getMicrotime() - simulationStartTime > lifetime){
			printf("The current CPU utilization is (percent): %Lf\n", loadavg * 100/cnt);
			printf("=========================================================\n");
			FILE *fp;
		        fp = fopen(fileaddr,"a");
			fprintf(fp,"The current CPU utilization is (percent): %Lf\n", loadavg * 100/cnt);
			fclose(fp);

			break;
		}
		fp = fopen("/proc/stat","r");
		fscanf(fp,"%*s %Lf %Lf %Lf %Lf",&a[0],&a[1],&a[2],&a[3]);
		fclose(fp);
		sleep(1);

		fp = fopen("/proc/stat","r");
		fscanf(fp,"%*s %Lf %Lf %Lf %Lf",&b[0],&b[1],&b[2],&b[3]);
		fclose(fp);
		loadavg += ((b[0]+b[1]+b[2]) - (a[0]+a[1]+a[2])) / ((b[0]+b[1]+b[2]+b[3]) - (a[0]+a[1]+a[2]+a[3]));
		cnt++;
	}

	return(0);
}


int main(int argc, char **argv){
	long counter = 0;
	// Get server address and port from arguments
	if(argc != 7){
		printf("Invalid arguements: %s <address> <port> <duration(ms)> <verbType(READ/WRITE)> <memorySizetoRegister(Byte)> <logFileAdd>\n", argv[0]);
		return -1;
	}
	char *ip = argv[1];
	short port = atoi(argv[2]);
	lifetime= atoi(argv[3]);
	char *verbtype = argv[4];
	if (!strcmp(verbtype, "READ")){
		opcode = READ;
	}else if (!strcmp(verbtype , "WRITE")){
		opcode = WRITE;
	}else{
		printf("Invalid argument for method! I will use default value which is READ");
		opcode = READ;
	}
	REGION_LENGTH = atoi(argv[5]);
	fileaddr = argv[6];
	// Create the event channel
	struct rdma_event_channel *event_channel = rdma_create_event_channel();
	if(event_channel == NULL)
		stop_it("rdma_create_event_channel()", errno);
	// Create the ID
	struct rdma_cm_id *cm_id;
	if(rdma_create_id(event_channel, &cm_id, "qwerty", RDMA_PS_TCP))
		stop_it("rdma_create_id()", errno);
	// Connect to the server
	connect_four(cm_id, event_channel, ip, port);
	// Register memory region
	struct ibv_mr *mr = ibv_reg_mr(cm_id->qp->pd, malloc(REGION_LENGTH), REGION_LENGTH,
			IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_READ | IBV_ACCESS_REMOTE_WRITE);
	if(mr == NULL)
		stop_it("ibv_reg_mr()", errno);
	// Exchange addresses and rkeys with the server
	uint32_t rkey;
	uint64_t remote_addr;
	size_t server_mr_length;
	swap_info(cm_id, mr, &rkey, &remote_addr, &server_mr_length);
	// The real good
	void *buffer = malloc(MAX_INLINE_DATA);
	unsigned long long length;
	unsigned long long offset;
	unsigned char *byte;
	FILE *fp;
	fp = fopen(fileaddr,"w+");
	int ss=0;
	long simulationStartTime=getMicrotime();
	pthread_t id;
	int ret=pthread_create(&id,NULL,&cpu,NULL);
	if(ret==0){
		printf("Thread created successfully for CPU measurement.\n");
		printf("=========================================================\n\n");
	}

	while(1){
		counter++;
		if(getMicrotime() - simulationStartTime > lifetime ){
			if (opcode == WRITE){
				ss=(MAX_INLINE_DATA-1)* counter;
			}
			printf("\n======================== Reports ========================\n");
			printf("Throughput (Mb/s): %lf \n",(double) ss  * 8 / lifetime  );
			printf("Total number of packets: %ld \n",counter );
			printf("Total bytes sent: %d \n", ss  * 8);
			printf("Simulation length (ms): %ld \n", lifetime);
			printf("Average Delivery delay (us): %ld \n", totalDelay/counter);

			fprintf(fp,"Throughput (Mb/s): %lf \n",(double) ss  * 8 / lifetime  );
			fprintf(fp,"Total number of packets: %ld \n",counter );
			fprintf(fp,"Total bytes sent: %d \n", ss  * 8);
			fprintf(fp,"Simulation length (ms): %ld \n", lifetime);
			fprintf(fp,"Average Delivery delay (us): %ld \n", totalDelay/counter);

			rdma_send_op(cm_id, opcode);
			get_completion(cm_id, SEND, 0);
			break;
		}

		if(opcode == WRITE){
			offset = 0;
			if(offset+MAX_INLINE_DATA> server_mr_length){
				printf("Invalid offset.\n");
				continue;
			}
			memset(buffer, 0, MAX_INLINE_DATA);
			* (char *) buffer = MAX_INLINE_DATA-1;
			long tmp = getMicrotime();
			rdma_write_inline(cm_id, buffer, remote_addr+offset, rkey);
			get_completion(cm_id, SEND, 1);
			totalDelay += getMicrotime()-tmp;
		} else if(opcode == READ){
			offset=0;
			length=REGION_LENGTH;
			if(offset+length > server_mr_length || length > REGION_LENGTH){
				printf("Invalid offset and/or length.\n");
				continue;
			}
			long tmp = getMicrotime();
			if(rdma_post_read(cm_id, "qwerty", mr->addr, length, mr, IBV_SEND_SIGNALED,
						remote_addr + offset, rkey))
				stop_it("rdma_post_read()", errno);
			get_completion(cm_id, SEND, 1);
			totalDelay += getMicrotime()-tmp;
			byte = (unsigned char *)mr->addr;
			ss+=sizeof(byte);
		} else {
			printf("Unknown operation, try again buddy.\n");
		}

	}
	// Disconnect
	fclose(fp);
	obliterate(cm_id, NULL, mr, event_channel);
	return 0;
}

int connect_four(struct rdma_cm_id *cm_id, struct rdma_event_channel *ec, char *ip, 
		short int port){
	struct sockaddr_in sin;
	memset(&sin, 0, sizeof(struct sockaddr_in));
	sin.sin_family = AF_INET;
	sin.sin_port = htons(port);
	inet_aton(ip, &(sin.sin_addr));
	// Resolve the server's address
	if(rdma_resolve_addr(cm_id, NULL, (struct sockaddr *)&sin, 10000))
		stop_it("rdma_resolve_addr()", errno);
	// Wait for the address to resolve
	cm_event(ec, RDMA_CM_EVENT_ADDR_RESOLVED);
	// Create queue pair
	struct ibv_qp_init_attr *init_attr = malloc(sizeof(*init_attr));
	memset(init_attr, 0, sizeof(*init_attr));
	init_attr->qp_type = IBV_QPT_RC;
	init_attr->cap.max_send_wr  = MAX_SEND_WR;
	init_attr->cap.max_recv_wr  = MAX_RECV_WR;
	init_attr->cap.max_send_sge = MAX_SEND_SGE;
	init_attr->cap.max_recv_sge = MAX_RECV_SGE;
	init_attr->cap.max_inline_data = MAX_INLINE_DATA;
	if(rdma_create_qp(cm_id, NULL, init_attr))
		stop_it("rdma_create_qp()", errno);
	// Resolve the route to the server
	if(rdma_resolve_route(cm_id, 10000))
		stop_it("rdma_resolve_route()", errno);
	// Wait for the route to resolve
	cm_event(ec, RDMA_CM_EVENT_ROUTE_RESOLVED);
	// Send a connection request to the server
	struct rdma_conn_param *conn_params = malloc(sizeof(*conn_params));
	printf("\n======================= Statistics ======================\n");
	printf("Conencting...\n");
	memset(conn_params, 0, sizeof(*conn_params));
	conn_params->retry_count = 8;
	conn_params->rnr_retry_count = 8;
	conn_params->responder_resources = 10;
	conn_params->initiator_depth = 10;
	if(rdma_connect(cm_id, conn_params))
		stop_it("rdma_connect()", errno);
	// Wait for the server to accept the connection
	cm_event(ec, RDMA_CM_EVENT_ESTABLISHED);
	return 0;
}
