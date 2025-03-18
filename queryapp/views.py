# from django.shortcuts import render, redirect
# from django.http import HttpResponse
# from agent.ai_agent import run_sql_agent, fix_and_retry_query
# from django.views.decorators.csrf import csrf_exempt

def test_view(request):
    return HttpResponse("NGROK is working!")


# @csrf_exempt
# def query_ai_view(request):
#     # Only clear session if browser reload is detected
#     if request.GET.get("reload") == "true":
#         request.session.flush()
#         return redirect("query-ai")

#     if request.method == "POST":
#         user_query = request.POST.get("user_query", "").strip()

#         if user_query:
#             sql_query = run_sql_agent(user_query)
#             if sql_query:
#                 result, error = fix_and_retry_query(sql_query, error_message="")

#                 request.session["sql_query"] = sql_query
#                 request.session["user_query"] = user_query

#                 if error:
#                     request.session["error_message"] = error
#                     request.session["query_result"] = None
#                 else:
#                     request.session["error_message"] = None
#                     request.session["query_result"] = result

#                 request.session.modified = True
#                 request.session.save()

#     context = {
#         "user_query": request.session.get("user_query", ""),
#         "sql_query": request.session.get("sql_query", ""),
#         "query_result": request.session.get("query_result", []),
#         "error_message": request.session.get("error_message", ""),
#     }

#     return render(request, "queryapp/query.html", context)


from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from agent.ai_agent import run_sql_agent
import logging

# Configure logging
logging.basicConfig(filename="views.log", level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s")

def test_view(request):
    return HttpResponse("NGROK is working!")

@csrf_exempt
def query_ai_view(request):
    # Handle browser reload by clearing the session
    if request.GET.get("reload") == "true":
        request.session.flush()
        return redirect("query-ai")

    if request.method == "POST":
        user_query = request.POST.get("user_query", "").strip()

        if user_query:
            logging.info(f"User Query: {user_query}")

            result = run_sql_agent(user_query)
            
            # Determine response type based on result structure
            if isinstance(result, str) and result.startswith("❌"):
                request.session["error_message"] = result
                request.session["query_result"] = None
            else:
                request.session["error_message"] = None
                request.session["query_result"] = result
            
            request.session["user_query"] = user_query
            request.session.modified = True
            request.session.save()
    
    context = {
        "user_query": request.session.get("user_query", ""),
        "query_result": request.session.get("query_result", []),
        "error_message": request.session.get("error_message", ""),
    }

    return render(request, "queryapp/query.html", context)
