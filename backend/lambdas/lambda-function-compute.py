import json
import boto3
import os
import uuid
import base64
import pathlib
import datatier
import urllib.parse
import string
import concurrent.futures

from configparser import ConfigParser
from pypdf import PdfReader

def call_bedrock(model_id, prompt):
    """
    Function to call AWS Bedrock with the given prompt.
    """
    bedrock = boto3.client('bedrock-runtime')

    payload = {
        "prompt": prompt,
        "max_gen_len": 1024, 
        "temperature": 0.7,
        "top_p": 0.9
    }

    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(payload)
    )

    # Read response
    response_body = json.loads(response['body'].read())
    return response_body.get("generation", "No response generated.")

def lambda_handler(event, context):
    try:
        print("**STARTING**")
        print("**lambda: proj_final_compute**")

        # Initial filename for error handling
        bucketkey_results_file = ""

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

        # Get S3 bucket key from the event
        bucketkey = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

        print("bucketkey:", bucketkey)

        if not bucketkey.endswith(".pdf"):
            raise Exception("Expecting S3 document to have .pdf extension")

        bucketkey_results_file = bucketkey.replace(".pdf", "-rating.txt")
        bucketkey_advice_file = bucketkey.replace(".pdf", "-advice.txt")
        bucketkey_cover_letter_file = bucketkey.replace(".pdf", "-cover_letter.txt")

        print("Result file:", bucketkey_results_file)
        print("Advice file:", bucketkey_advice_file)
        print("Cover Letter file:", bucketkey_cover_letter_file)

        # Download PDF from S3
        print("**DOWNLOADING '", bucketkey, "'**")
        local_pdf = "/tmp/data.pdf"
        bucket.download_file(bucketkey, local_pdf)

        # Extract text from the PDF
        print("**PROCESSING local PDF**")
        reader = PdfReader(local_pdf)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

        print("Extracted Text (First 100 chars):", text[:100])

        # Bedrock Model ID
        MODEL_ID = "us.meta.llama3-1-8b-instruct-v1:0"

        # Define prompts for Bedrock calls
        skill_extraction_prompt = f"""
        <|begin_of_text|><|start_header_id|>user<|end_header_id|>
        You are a helpful assistant extracting key skill sets from the resume and job description below.
        
        {text} 
        
        Provide a JSON response with:
        {{
            "resume_skills": A list of top 10 key skills from the resume,
            "description_skills": A list of top 10 key skills from the job description,
            "score": A score (1-100) representing the skill match based on the resume_skills and description_skills
        }}
        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        """

        modification_advice_prompt = f"""
        <|begin_of_text|><|start_header_id|>user<|end_header_id|>
        You are an expert resume reviewer. 
        Analyze the resume and job description text below and provide recommendations on how to improve it for the given job description.
        Be as specific as possible.
        
        {text}
        
        Provide a JSON response with:
        {{
            "advice": A list of 5 text descriptions for improvement
        }}
        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        """

        cover_letter_prompt = f"""
        <|begin_of_text|><|start_header_id|>user<|end_header_id|>
        You are a professional career advisor. 
        Using the resume and job description details below, write a well-structured, concise, and compelling cover letter.
        
        {text}
        
        The cover letter should have:
        - A strong introduction highlighting enthusiasm for the role
        - Key skills and experiences relevant to the job description
        - A closing paragraph reinforcing interest and a call to action

        Provide a JSON response with:
        {{
            "letter": The full cover letter
        }}
        <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        """

        # Run Bedrock Calls in Parallel
        print("**Calling Bedrock in Parallel**")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_results = {
                "skills": executor.submit(call_bedrock, MODEL_ID, skill_extraction_prompt),
                "advice": executor.submit(call_bedrock, MODEL_ID, modification_advice_prompt),
                "cover_letter": executor.submit(call_bedrock, MODEL_ID, cover_letter_prompt)
            }

            # Get responses
            generated_response = {key: future.result() for key, future in future_results.items()}

        print("Generated Responses:", generated_response)

        # Save results to local files
        for key, filename in [
            ("skills", bucketkey_results_file),
            ("advice", bucketkey_advice_file),
            ("cover_letter", bucketkey_cover_letter_file)
        ]:
            new_path = filename.replace('resumeapp/', '/') 
            local_file = f"/tmp/{new_path}"
            with open(local_file, "w") as file:
                file.write(generated_response[key])

            print(f"Uploading {filename} to S3")
            bucket.upload_file(local_file, filename, ExtraArgs={'ACL': 'public-read', 'ContentType': 'text/plain'})

        # Update database with results
        sql_complete_cmd = '''
          UPDATE jobs
          SET ratingbucketkey = %s,
              advicebucketkey = %s,
              letterbucketkey = %s
          WHERE bucketkey = %s;
        '''

        print("**Opening DB connection**")
    
        dbConn = datatier.get_dbConn(rds_endpoint, rds_portnum, rds_username, rds_pwd, rds_dbname)
        datatier.perform_action(dbConn, sql_complete_cmd, [bucketkey_results_file, bucketkey_advice_file, bucketkey_cover_letter_file, bucketkey])

        print("**DONE, returning success**")

        return {
            'statusCode': 200,
            'body': json.dumps("success")
        }

    except Exception as err:
        print("**ERROR**", str(err))
        return {
            'statusCode': 500,
            'body': json.dumps(str(err))
        }