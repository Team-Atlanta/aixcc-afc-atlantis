## JAVA Method-Level tracer

this tracer traces which methods calls other methods

### output format

```json
{
    thread_id: [
    {
        "caller": { // This is caller function's information field
            "file": "File location where caller method defined",
            "prototype": "dummy value",
            "class_name": "caller method's class name",
            "method_name": "caller method name"
        },
        "callees": { // This is information field that callee methods caller called 
            "file": "file path where the caller called",
            "line": "line number where the caller called",
            "callee": { // callee information
                "file": "file path where callee function defined",
                "prototype": "callee method's prototype",
                "class_name": "callee method's class name",
                "method_name": "callee method name"
            }
        }
    }
    ...
  ],
  thread_id_2: [] ...
}
```

### output example (for mock-java):

```
{
  "1": [
    {
      "caller": {
        "file": "Unknown",
        "prototype": "Unknown",
        "class_name": "Unknown",
        "method_name": "Unknown"
      },
      "callees": [
        {
          "file": "Unknown",
          "line": -1,
          "callee": {
            "file": "OssFuzz1.java",
            "prototype": "(Lcom/code_intelligence/jazzer/api/FuzzedDataProvider;)V",
            "class_name": "OssFuzz1",
            "method_name": "fuzzerTestOneInput"
          }
        }
      ]
    },
    {
      "caller": {
        "file": "OssFuzz1.java",
        "prototype": "(Lcom/code_intelligence/jazzer/api/FuzzedDataProvider;)V",
        "class_name": "OssFuzz1",
        "method_name": "fuzzerTestOneInput"
      },
      "callees": [
        {
          "file": "OssFuzz1.java",
          "line": 13,
          "callee": {
            "file": "App.java",
            "prototype": "(Ljava/lang/String;)V",
            "class_name": "com.aixcc.mock_java.App",
            "method_name": "executeCommand"
          }
        }
      ]
    },
    {
      "caller": {
        "file": "App.java",
        "prototype": "(Ljava/lang/String;)V",
        "class_name": "com.aixcc.mock_java.App",
        "method_name": "executeCommand"
      },
      "callees": [
        {
          "file": "App.java",
          "line": 16,
          "callee": {
            "file": "OssFuzz1.java",
            "prototype": "(Lcom/code_intelligence/jazzer/api/FuzzedDataProvider;)V",
            "class_name": "OssFuzz1",
            "method_name": "fuzzerTestOneInput"
          }
        }
      ]
    },
    {
      "caller": {
        "file": "OssFuzz1.java",
        "prototype": "(Lcom/code_intelligence/jazzer/api/FuzzedDataProvider;)V",
        "class_name": "OssFuzz1",
        "method_name": "fuzzerTestOneInput"
      },
      "callees": [
        {
          "file": "OssFuzz1.java",
          "line": 13,
          "callee": {
            "file": "App.java",
            "prototype": "(Ljava/lang/String;)V",
            "class_name": "com.aixcc.mock_java.App",
            "method_name": "executeCommand"
          }
        }
      ]
    }
  ]
}


```
