import json
import boto3
import os
import uuid
import base64
import io
import datatier
import PyPDF2
from configparser import ConfigParser

def lambda_handler(event, context):
    try:
        print("**STARTING**")
        print("**lambda: proj_final_upload**")

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

        print("**Accessing request body**")

        if "body" not in event:
            raise Exception("event has no body")

        body = json.loads(event["body"])  # Parse the JSON

        print("Request Body: ", body)

        if "resumedata" not in body:
            raise Exception("event has a body but no resume data")
        if "descriptiondata" not in body:
            raise Exception("event has a body but no description data")

        resume_datastr = body["resumedata"]
        description_datastr = body["descriptiondata"]

        print("resume datastr (first 10 chars):", resume_datastr[0:10])
        print("description datastr (first 10 chars):", description_datastr[0:10])

        # Open connection to the database
        print("**Opening connection**")
        dbConn = datatier.get_dbConn(rds_endpoint, rds_portnum, rds_username, rds_pwd, rds_dbname)

        # Decode Base64 data
        resume_bytes = base64.b64decode(resume_datastr.encode())
        description_bytes = base64.b64decode(description_datastr.encode())

        # Convert bytes to file-like objects
        resume_pdf_reader = PyPDF2.PdfReader(io.BytesIO(resume_bytes))
        description_pdf_reader = PyPDF2.PdfReader(io.BytesIO(description_bytes))

        # Create a PDF writer to combine both files
        pdf_writer = PyPDF2.PdfWriter()

        # Add all pages from the resume PDF
        for page in resume_pdf_reader.pages:
            pdf_writer.add_page(page)

        # Add all pages from the description PDF
        for page in description_pdf_reader.pages:
            pdf_writer.add_page(page)

        # Save to local temp file
        local_filename = "/tmp/combined_resume.pdf"
        with open(local_filename, "wb") as f:
            pdf_writer.write(f)

        # Generate unique filename in S3
        print("**Uploading local file to S3**")
        bucketkey = "resumeapp/" + str(uuid.uuid4()) + ".pdf"

        print("S3 bucketkey:", bucketkey)

        # Insert into DB
        print("**Adding jobs row to database**")
        sql = """INSERT INTO jobs(bucketkey, ratingbucketkey, advicebucketkey, letterbucketkey)
                  VALUES(%s, '', '', '');"""
        datatier.perform_action(dbConn, sql, [bucketkey])

        # Retrieve Job ID
        sql = "SELECT LAST_INSERT_ID();"
        row = datatier.retrieve_one_row(dbConn, sql)
        jobid = row[0]

        print("jobid:", jobid)

        # Upload PDF to S3
        print("**Uploading data file to S3**")
        bucket.upload_file(local_filename,
                           bucketkey,
                           ExtraArgs={
                               'ACL': 'public-read',
                               'ContentType': 'application/pdf'
                           })

        print("**DONE, returning jobid**")
        return {
            'statusCode': 200,
            'body': json.dumps(str(jobid))
        }

    except Exception as err:
        print("**ERROR**")
        print(str(err))

        return {
            'statusCode': 500,
            'body': json.dumps(str(err))
        }
