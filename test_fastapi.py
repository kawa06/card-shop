from fastapi import FastAPI, Query
app = FastAPI()
@app.get('/')
def read_items(sort: str = Query('created_at_desc', regex='^(price_asc|price_desc|name_asc|created_at_desc)$')):
    return {'sort': sort}
