import json
import boto3
import os
import base64
import datatier

from configparser import ConfigParser

def lambda_handler(event, context):
    try:
        print("**STARTING**")
        print("**lambda: proj_final_download**")

        # Setup AWS based on config file
        config_file = 'resumeapp-config.ini'
        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = config_file

        configur = ConfigParser()
        configur.read(config_file)

        # Configure for S3 access
        s3_profile = 's3readwrite'
        boto3.setup_default_session(profile_name=s3_profile)

        bucketname = configur.get('s3', 'bucket_name')

        s3 = boto3.resource('s3')
        bucket = s3.Bucket(bucketname)

        # Configure for RDS access
        rds_endpoint = configur.get('rds', 'endpoint')
        rds_portnum = int(configur.get('rds', 'port_number'))
        rds_username = configur.get('rds', 'user_name')
        rds_pwd = configur.get('rds', 'user_pwd')
        rds_dbname = configur.get('rds', 'db_name')

        # Extract jobid from request
        if "jobid" in event:
            jobid = event["jobid"]
        elif "pathParameters" in event and "jobid" in event["pathParameters"]:
            jobid = event["pathParameters"]["jobid"]
        else:
            raise Exception("Job ID is required in the request.")

        print("Job ID:", jobid)

        # Open DB connection
        print("**Opening DB connection**")
        dbConn = datatier.get_dbConn(rds_endpoint, rds_portnum, rds_username, rds_pwd, rds_dbname)

        # Query the database for job details
        print("**Checking job status**")
        sql = "SELECT bucketkey, ratingbucketkey, advicebucketkey, letterbucketkey FROM jobs WHERE jobid = %s;"
        row = datatier.retrieve_one_row(dbConn, sql, [jobid])

        if not row:
            print("**No such job found**")
            return {
                'statusCode': 400,
                'body': json.dumps({"error": "No such job exists."})
            }

        bucketkey, ratingbucketkey, advicebucketkey, letterbucketkey = row
        print("Bucket Keys:", bucketkey, ratingbucketkey, advicebucketkey, letterbucketkey)

        # If any result file key is missing, job is still processing
        if not all([ratingbucketkey, advicebucketkey, letterbucketkey]):
            print("**Job still processing...**")
            return {
                'statusCode': 202,  # Still Processing
                'body': json.dumps({"status": "processing"})
            }

        # Function to download and read an S3 file
        def fetch_s3_file(bucket, file_key):
            local_path = f"/tmp/{file_key.split('/')[-1]}"  
            bucket.download_file(file_key, local_path)
            with open(local_path, "r") as f:
                return f.read().strip()

        # Download and read results
        print("**Downloading results from S3**")
        rating_results = fetch_s3_file(bucket, ratingbucketkey)
        advice_results = fetch_s3_file(bucket, advicebucketkey)
        cover_letter_results = fetch_s3_file(bucket, letterbucketkey)

        # Prepare the JSON response
        response_json = {
            "jobid": jobid,
            "status": "completed",
            "results": {
                "skills_analysis": rating_results,
                "resume_advice": advice_results,
                "cover_letter": cover_letter_results
            }
        }

        print("**DONE, returning results**")
        return {
            'statusCode': 200,
            'body': json.dumps(response_json)
        }

    except Exception as err:
        print("**ERROR**", str(err))
        return {
            'statusCode': 500,
            'body': json.dumps({"error": str(err)})
        }