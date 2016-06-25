//
//  python_wrapper.c
//  LRUAnalyzer
//
//  Created by Juncheng on 5/26/16.
//  Copyright © 2016 Juncheng. All rights reserved.
//

#include <Python.h>

#define NPY_NO_DEPRECATED_API 11
#include <numpy/arrayobject.h>

#include "generalProfiler.h"
#include "FIFO.h"
#include "Optimal.h"
#include <math.h>


/* TODO:
 not urgent, not necessary: change this profiler module into a pyhton object,
 this is not necessary for now because we are not going to expose this level API
 to user, instead we wrap it with our python API, so these C functions are only
 called inside mimircache
 */


static PyObject* generalProfiler_get_hit_rate(PyObject* self, PyObject* args, PyObject* keywds)
{
    PyObject* po;
    READER* reader;
    int num_of_threads = 4;
    long cache_size;
    int bin_size = -1;
    char* name;
    struct_cache* cache;
    PyObject* cache_params;
    
    long begin=0, end=-1;
    static char *kwlist[] = {"reader", "cache_name", "cache_size", "bin_size", "cache_params", "num_of_threads", "begin", "end", NULL};
    
    // parse arguments
    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Osli|Oill", kwlist, &po, &name, &cache_size, &bin_size, &cache_params, &num_of_threads, &begin, &end)) {
        printf("parsing argument failed in generalProfiler_get_hit_rate\n");
        return NULL;
    }
    
    if(begin == -1)
        begin = 0;
        
    printf("bin size: %d, threads: %d\n", bin_size, num_of_threads);
    
    if (!(reader = (READER*) PyCapsule_GetPointer(po, NULL))) {
        return NULL;
    }

    // build cache
    char data_type = reader->type;
    
    if (strcmp(name, "FIFO") == 0){
        cache = fifo_init(cache_size, data_type, NULL);

    }
    else if (strcmp(name, "Optimal") == 0){
        struct optimal_init_params init_params = {.reader=reader, .next_access=NULL, .ts=begin};
        cache = optimal_init(cache_size, data_type, (void*)&init_params);
    }
    else {
        printf("does not support given cache replacement algorithm: %s\n", name);
        exit(1);
    }
    
    // get hit rate
    DEBUG(printf("before profiling\n"));
    return_res** results = profiler(reader, cache, num_of_threads, bin_size, (gint64)begin, (gint64)end);
    DEBUG(printf("after profiling\n"));
    
    // create numpy array 
    guint num_of_bins = ceil(cache_size/bin_size)+1;
    npy_intp dims[1] = { num_of_bins };
    PyObject* ret_array = PyArray_SimpleNew(1, dims, NPY_DOUBLE);
    guint i;
    *(double*)PyArray_GETPTR1((PyArrayObject*)ret_array, 0) = 0;
    for(i=1; i<num_of_bins; i++){
        *(double*)PyArray_GETPTR1((PyArrayObject*)ret_array, i) = results[i-1]->hit_rate;
        free(results[i-1]);
    }
    
//    PyObject *d = PyDict_New();
//    for (i=0; i<num_of_bins; i++){
//        PyDict_SetItem(d, Py_BuildValue("l", (i+1)*bin_size), Py_BuildValue("f", results[i]->hit_rate));
//    }
    
    free(results);
    cache->core->destroy(cache);
    return ret_array;
}









static PyObject* generalProfiler_get_hit_count(PyObject* self, PyObject* args, PyObject* keywds)
{
    PyObject* po;
    READER* reader;
    int num_of_threads = 4;
    long cache_size;
    int bin_size = -1;
    char* name;
    struct_cache* cache;
    PyObject* cache_params;
    
    long begin=0, end=-1;
    static char *kwlist[] = {"reader", "cache_name", "cache_size", "bin_size", "cache_params", "num_of_threads", "begin", "end", NULL};
    
    // parse arguments
    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Osli|Oill", kwlist, &po, &name, &cache_size, &bin_size, &cache_params, &num_of_threads, &begin, &end)) {
        printf("parsing argument failed in generalProfiler_get_hit_rate\n");
        return NULL;
    }
    
    if(begin == -1)
        begin = 0;
    
    printf("bin size: %d, threads: %d\n", bin_size, num_of_threads);
    
    if (!(reader = (READER*) PyCapsule_GetPointer(po, NULL))) {
        return NULL;
    }
    
    // build cache
    char data_type = reader->type;
    
    if (strcmp(name, "FIFO") == 0){
        cache = fifo_init(cache_size, data_type, NULL);
        
    }
    else if (strcmp(name, "Optimal") == 0){
        struct optimal_init_params init_params = {.reader=reader, .next_access=NULL, .ts=begin};
        cache = optimal_init(cache_size, data_type, (void*)&init_params);
    }
    else {
        printf("does not support given cache replacement algorithm: %s\n", name);
        exit(1);
    }
    
    // get hit rate
    DEBUG(printf("before profiling\n"));
    return_res** results = profiler(reader, cache, num_of_threads, bin_size, (gint64)begin, (gint64)end);
    DEBUG(printf("after profiling\n"));
    
    // create numpy array
    guint num_of_bins = ceil(cache_size/bin_size)+1;
    npy_intp dims[1] = { num_of_bins };
    PyObject* ret_array = PyArray_SimpleNew(1, dims, NPY_LONGLONG);
    guint i;
    *(long*)PyArray_GETPTR1((PyArrayObject*)ret_array, 0) = 0;
    for(i=1; i<num_of_bins; i++){
        *(long*)PyArray_GETPTR1((PyArrayObject*)ret_array, i) = results[i-1]->hit_count;
        free(results[i-1]);
    }
    

    free(results);
    cache->core->destroy(cache);
    return ret_array;
}


static PyObject* generalProfiler_get_miss_rate(PyObject* self, PyObject* args, PyObject* keywds)
{
    PyObject* po;
    READER* reader;
    int num_of_threads = 4;
    long cache_size;
    int bin_size = -1;
    char* name;
    struct_cache* cache;
    PyObject* cache_params;
    
    long begin=0, end=-1;
    static char *kwlist[] = {"reader", "cache_name", "cache_size", "bin_size", "cache_params", "num_of_threads", "begin", "end", NULL};
    
    // parse arguments
    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Osli|Oill", kwlist, &po, &name, &cache_size, &bin_size, &cache_params, &num_of_threads, &begin, &end)) {
        printf("parsing argument failed in generalProfiler_get_hit_rate\n");
        return NULL;
    }
    
    if(begin == -1)
        begin = 0;
    
    printf("bin size: %d, threads: %d\n", bin_size, num_of_threads);
    
    if (!(reader = (READER*) PyCapsule_GetPointer(po, NULL))) {
        return NULL;
    }
    
    // build cache
    char data_type = reader->type;
    
    if (strcmp(name, "FIFO") == 0){
        cache = fifo_init(cache_size, data_type, NULL);
        
    }
    else if (strcmp(name, "Optimal") == 0){
        struct optimal_init_params init_params = {.reader=reader, .next_access=NULL, .ts=begin};
        cache = optimal_init(cache_size, data_type, (void*)&init_params);
    }
    else {
        printf("does not support given cache replacement algorithm: %s\n", name);
        exit(1);
    }
    
    // get hit rate
    DEBUG(printf("before profiling\n"));
    return_res** results = profiler(reader, cache, num_of_threads, bin_size, (gint64)begin, (gint64)end);
    DEBUG(printf("after profiling\n"));
    
    // create numpy array
    guint num_of_bins = ceil(cache_size/bin_size)+1;
    npy_intp dims[1] = { num_of_bins };
    PyObject* ret_array = PyArray_SimpleNew(1, dims, NPY_DOUBLE);
    guint i;
    *(double*)PyArray_GETPTR1((PyArrayObject*)ret_array, 0) = 0;
    for(i=1; i<num_of_bins; i++){
        *(double*)PyArray_GETPTR1((PyArrayObject*)ret_array, i) = results[i-1]->miss_rate;
        free(results[i-1]);
    }
    
    
    free(results);
    cache->core->destroy(cache);
    return ret_array;
}




static PyMethodDef c_generalProfiler_funcs[] = {
    {"get_hit_rate", (PyCFunction)generalProfiler_get_hit_rate,
        METH_VARARGS | METH_KEYWORDS, "get hit rate numpy array"},
    {"get_hit_count", (PyCFunction)generalProfiler_get_hit_count,
        METH_VARARGS | METH_KEYWORDS, "get hit count numpy array"},
    {"get_miss_rate", (PyCFunction)generalProfiler_get_miss_rate,
        METH_VARARGS | METH_KEYWORDS, "get miss rate numpy array"},
    {NULL, NULL, 0, NULL}
};


static struct PyModuleDef c_generalProfiler_definition = {
    PyModuleDef_HEAD_INIT,
    "c_generalProfiler",
    "A Python module that doing profiling with regards to all kinds of caches",
    -1,
    c_generalProfiler_funcs
};



PyMODINIT_FUNC PyInit_c_generalProfiler(void)
{
    Py_Initialize();
    import_array();
    return PyModule_Create(&c_generalProfiler_definition);
}

