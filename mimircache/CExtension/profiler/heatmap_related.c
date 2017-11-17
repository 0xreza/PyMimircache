//
//  heatmat_related.c
//  mimircache
//
//  Created by Juncheng on 5/24/16.
//  Copyright © 2016 Juncheng. All rights reserved.
//



#include "heatmap.h"
#include "csvReader.h"
#include "binaryReader.h"


#ifdef __cplusplus
extern "C"
{
#endif




double get_log_base(guint64 max, guint64 expect_result){
    
    double base = 10;
    double result, prev_result = expect_result;
    while (1){
        result = log((double)max)/log(base);
        if (result>expect_result && prev_result<expect_result)
            return base;
        prev_result = result;
        base = (base - 1)/2 + 1;
    }
}

static inline gint process_one_element_last_access(cache_line* cp,
                                                   GHashTable* hash_table,
                                                   guint64 ts);


/*-----------------------------------------------------------------------------
 *
 * get_last_access_dist_seq --
 *      this function returns how far away one request was requested in the past,
 *      if it was not requested before, then -1;
 *      it can be run forward or backward depends on the paaed reading func
 *      when running forward, it gives how far in the past of its last request,
 *      when running backward, it gives how far away in the future
 *      it will be requested again.
 *      ATTENTION: when running backward, the returned list is also REVERSED
 *
 * Potential bug:
 *      this function currently using int, may cause some problem when the
 *      trace file is tooooooo large
 *
 * Input:
 *      reader:         the reader for data
 *      funcPtr:        how to read data, can be read_one_element or 
 *                      read_one_element_above
 *
 * Return:
 *      GSList* contains the distance to last access
 *
 *-----------------------------------------------------------------------------
 */

GSList* get_last_access_dist_seq(reader_t* reader,
                                 void (*funcPtr)(reader_t*, cache_line*)){


    GSList* list= NULL; 

    if (reader->base->total_num == -1)
        get_num_of_req(reader);

    // create cache lize struct and initialization
    cache_line* cp = new_cacheline();
    cp->type = reader->base->data_type;
    cp->block_unit_size = (size_t) reader->base->block_unit_size;

    // create hashtable
    GHashTable * hash_table; 
    if (cp->type == 'l'){
        hash_table = g_hash_table_new_full(g_int64_hash, g_int64_equal, \
                                            (GDestroyNotify)simple_g_key_value_destroyer, \
                                            (GDestroyNotify)simple_g_key_value_destroyer);
    }
    else if (cp->type == 'c'){
        hash_table = g_hash_table_new_full(g_str_hash, g_str_equal, \
                                            (GDestroyNotify)simple_g_key_value_destroyer, \
                                            (GDestroyNotify)simple_g_key_value_destroyer);
    }
    else{
        ERROR("unknown data type: %c\n", cp->type);
        abort();
    }
    
    guint64 ts = 0;
    gint dist;

    if (funcPtr == read_one_element){
        read_one_element(reader, cp);
    }
    else if (funcPtr == read_one_element_above){
        reader_set_read_pos(reader, 1.0);
        if (go_back_one_line(reader)!=0)
            ERROR("error when going back one line\n");
        read_one_element(reader, cp);
        set_no_eof(reader);
    }
    else{
        ERROR("unknown function pointer received in heatmap\n");
        abort();
    }

    while (cp->valid){
        dist = process_one_element_last_access(cp, hash_table, ts);
        list = g_slist_prepend(list, GINT_TO_POINTER(dist));
        funcPtr(reader, cp);
        ts++;
    }
    if (reader->base->type == 'c'){
        csv_params_t *params = reader->reader_params;
        if (params->has_header)
            list = g_slist_remove(list, list->data);
    }


    // clean up
    g_free(cp);
    g_hash_table_destroy(hash_table);
    reset_reader(reader);
    return list;
}


/*-----------------------------------------------------------------------------
 *
 * process_one_element_last_access --
 *      this function is called by get_last_access_dist_seq,
 *      it insert current request and return distance to its last request
 *
 * Potential bug:
 *      No
 *
 * Input:
 *      cp:             cache_line contains current request
 *      hash_table:     the hashtable for remembering last access
 *      ts:             current timestamp
 *
 *
 * Return:
 *      distance to last request 
 *
 *-----------------------------------------------------------------------------
 */

static inline gint process_one_element_last_access(cache_line* cp,
                                                   GHashTable* hash_table,
                                                   guint64 ts){
    gpointer gp;
    gp = g_hash_table_lookup(hash_table, cp->item);
    gint ret;
    if (gp == NULL){
        // first time access
        ret = -1;
        guint64* value = g_new(guint64, 1);
        *value = ts;
        if (cp->type == 'c') 
            g_hash_table_insert(hash_table,
                                g_strdup((gchar*)(cp->item_p)),
                                (gpointer)value);
        
        else if (cp->type == 'l'){
            guint64* key = g_new(guint64, 1);
            *key = *(guint64*)(cp->item_p);
            g_hash_table_insert(hash_table,
                                (gpointer)(key),
                                (gpointer)value);
        }
        else{
            ERROR("unknown cache line content type: %c\n", cp->type);
            exit(1);
        }
    }
    else{
        // not first time access
        guint64 old_ts = *(guint64*)gp;
        ret = (gint) (ts - old_ts);
        *(guint64*)gp = ts;
    }
    return ret;
}


GArray* gen_breakpoints_virtualtime(reader_t* reader,
                                    gint64 time_interval,
                                    gint64 num_of_piexls){
    /* 
     return a GArray of break points, including the last break points
     */
    
    if (reader->base->total_num == -1)
        get_num_of_req(reader);
    
    if (reader->sdata->break_points){
        if (reader->sdata->break_points->mode == 'v' &&
            (long) reader->sdata->break_points->time_interval == time_interval )
            return reader->sdata->break_points->array;
        else{
            g_array_free(reader->sdata->break_points->array, TRUE);
            free(reader->sdata->break_points);
        }
    }
    
    gint i;
    gint array_size = (gint) num_of_piexls;
    if (array_size==-1)
        array_size = (gint) ceil((double) reader->base->total_num/time_interval + 1);
    else
        time_interval = (gint) ceil((double) reader->base->total_num/num_of_piexls + 1);
//    array_size ++ ;
    
    GArray* break_points = g_array_sized_new(FALSE, FALSE, sizeof(guint64), array_size);
    for (i=0; i<array_size-1; i++){
        guint64 value = i * time_interval;
        g_array_append_val(break_points, value);
    }
    g_array_append_val(break_points, reader->base->total_num);
    
    
    if (break_points->len > 10000){
        WARNING("%snumber of pixels in one dimension is larger than 10000, "
                "exact size: %d, it may take a very long time, if you didn't "
                "intend to do it, please try with a larger time stamp%s\n",
                KRED, break_points->len, KRESET);
    }
    else if (break_points->len < 20){
        WARNING("%snumber of pixels in one dimension is smaller than 20, "
                "exact size: %d, each pixel will be very large, if you didn't "
                "intend to do this, please try with a smaller time stamp%s\n",
                KRED, break_points->len, KRESET);
    }
    
    struct break_point* bp = g_new(struct break_point, 1);
    bp->mode = 'v';
    bp->time_interval = time_interval;
    bp->array = break_points;
    reader->sdata->break_points = bp;

    reset_reader(reader);
    return break_points;
}


GArray* gen_breakpoints_realtime(reader_t* reader,
                                 gint64 time_interval,
                                 gint64 num_of_piexls){
    /*
     currently this only works for vscsi reader !!!
     return a GArray of break points, including the last break points
     */
    if (reader->base->type == 'p'){
        printf("gen_breakpoints_realtime currently don't support plain reader, program exit\n");
        exit(1);
    }
    if (reader->base->type == 'c'){
        csv_params_t* params = reader->reader_params;
        if (params->real_time_column == -1 || params->real_time_column == 0){
            ERROR("gen_breakpoints_realtime needs you to provide "
                  "real_time_column parameter for csv reader\n");
            exit(1);
        }
    }
    if (reader->base->type == 'b'){
        binary_params_t* params = reader->reader_params;
        if (params->real_time_pos == 0){
            ERROR("gen_breakpoints_realtime needs you to provide "
                  "real_time parameter for binary reader\n"); 
            exit(1);
        }
    }

    
    if (reader->base->total_num == -1)
        get_num_of_req(reader);
    
    
    if (reader->sdata->break_points){
        if (reader->sdata->break_points->mode == 'r' &&
            (long) reader->sdata->break_points->time_interval == time_interval ){
            return reader->sdata->break_points->array;
        }
        else{
            g_array_free(reader->sdata->break_points->array, TRUE);
            free(reader->sdata->break_points);
        }
    }
    
    guint64 previous_time = 0;
    GArray* break_points = g_array_new(FALSE, FALSE, sizeof(guint64));

    // create cache line struct and initialization
    cache_line* cp = new_cacheline();
    
    guint64 num = 0;
    
    reset_reader(reader);
    read_one_element(reader, cp);
    previous_time = cp->real_time;
    g_array_append_val(break_points, num);

    
    
    if (num_of_piexls != -1 && time_interval == -1){
        reader_set_read_pos(reader, 1);
        read_one_element_above(reader, cp);
        time_interval = (gint64) ceil( (double)(cp->real_time - previous_time) /num_of_piexls + 1);
        reader_set_read_pos(reader, 0);
        read_one_element(reader, cp);
    }
    
        
    while (cp->valid){
        if (cp->real_time - previous_time > (guint64)time_interval){
            g_array_append_val(break_points, num);
            previous_time = cp->real_time;
        }
        read_one_element(reader, cp);
        num++;
    }
    if ((gint64)g_array_index(break_points, guint64, break_points->len-1) != reader->base->total_num)
        g_array_append_val(break_points, reader->base->total_num);
    
    
    if (break_points->len > 10000){
        WARNING("%snumber of pixels in one dimension is larger than 10000, "
              "exact size: %d, it may take a very long time, if you didn't "
              "intend to do it, please try with a larger time stamp%s\n",
              KRED, break_points->len, KRESET);
    }
    else if (break_points->len < 20){
        WARNING("%snumber of pixels in one dimension is smaller than 20, "
              "exact size: %d, each pixel will be very large, if you didn't "
              "intend to do this, please try with a smaller time stamp%s\n",
              KRED, break_points->len, KRESET);
    }
    
    struct break_point* bp = g_new(struct break_point, 1);
    bp->mode = 'r';
    bp->time_interval = time_interval;
    bp->array = break_points;
    reader->sdata->break_points = bp;
    
    // clean up
    g_free(cp);
    reset_reader(reader);
    return break_points;
}


#ifdef __cplusplus
}
#endif
