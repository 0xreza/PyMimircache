# coding=utf-8

"""
this module offer the upper level API to user
"""
from matplotlib.ticker import FuncFormatter
import mimircache.c_heatmap as c_heatmap
from mimircache.profiler.evictionStat import *
from mimircache.profiler.twoDPlots import *
from mimircache.utils.prepPlotParams import *
from mimircache.cacheReader.traceStat import traceStat
from multiprocessing import cpu_count


class cachecow:
    all = ("open",
           "csv",
           "vscsi",
           "binary",
           "stat",
           "num_of_req",
           "num_of_uniq_req",
           "get_reuse_distance",
           "get_hit_ratio_dict",
           "heatmap",
           "diffHeatmap",
           "twoDPlot",
           "eviction_plot",
           "plotHRCs",
           "plotMRCs",
           "characterize",
           "close")

    def __init__(self, **kwargs):
        self.reader = None
        self.cache_size = 0
        self.n_req = -1
        self.n_uniq_req = -1
        self.cacheclass_mapping = {}

    def open(self, file_path, trace_type="p", **kwargs):
        """
        default this opens a plain text file, which contains a label each line
        but it also supports only other type of trace by setting trace_type
        the parameters for opening other trace type are the same as corresponding call
        :param file_path:
        :param trace_type:
        :param kwargs:
        :return:
        """
        if trace_type == "p":
            if self.reader:
                self.reader.close()
            self.reader = plainReader(file_path, data_type=kwargs.get("data_type", "c"))

        elif trace_type == "c":
            assert "init_params" in kwargs, "please provide init_params for csv trace"
            init_params = kwargs["init_params"]
            kwargs_new = {}
            kwargs_new.update(kwargs)
            del kwargs_new["init_params"]
            self.csv(file_path, init_params, **kwargs_new)

        elif trace_type == 'b':
            assert "init_params" in kwargs, "please provide init_params for csv trace"
            init_params = kwargs["init_params"]
            kwargs_new = {}
            kwargs_new.update(kwargs)
            del kwargs_new["init_params"]
            self.binary(file_path, init_params, **kwargs_new)

        elif trace_type == 'v':
            self.vscsi(file_path, **kwargs)

        else:
            raise RuntimeError("unknown trace type {}".format(trace_type))

        return self.reader

    def csv(self, file_path, init_params, data_type='c', block_unit_size=0, disk_sector_size=0):
        """
        open a csv file
        :param file_path:
        :param init_params: params related to csv file, see csvReader for detail
        :param data_type: can be either 'c' for string or 'l' for number (like block IO)
        :param block_unit_size: the page size for a cache
        :param disk_sector_size: the disk sector size of input file
        :return:
        """
        if self.reader:
            self.reader.close()
        self.reader = csvReader(file_path, data_type=data_type,
                                block_unit_size=block_unit_size,
                                disk_sector_size=disk_sector_size,
                                init_params=init_params)
        return self.reader

    def binary(self, file_path, init_params, data_type='l', block_unit_size=0, disk_sector_size=0):
        """
        open a binary file
        :param file_path:
        :param init_params: params related to csv file, see csvReader for detail
        :param data_type: can be either 'c' for string or 'l' for number (like block IO)
        :param block_unit_size: the page size for a cache
        :param disk_sector_size: the disk sector size of input file
        :return:
        """
        if self.reader:
            self.reader.close()
        self.reader = binaryReader(file_path, data_type=data_type,
                                   block_unit_size=block_unit_size,
                                   disk_sector_size=disk_sector_size,
                                   init_params=init_params)
        return self.reader

    def vscsi(self, file_path, data_type='l', block_unit_size=0, disk_sector_size=512):
        """
        open vscsi trace file
        :param file_path:
        :param data_type: can be either 'c' for string or 'l' for number (like block IO)
        :param block_unit_size: the page size for a cache
        :param disk_sector_size: the disk sector size of input file
        :return:
        """
        if self.reader:
            self.reader.close()
        self.reader = vscsiReader(file_path, data_type=data_type,
                                  block_unit_size=block_unit_size,
                                  disk_sector_size=disk_sector_size)
        return self.reader

    def set_size(self, size):
        """
        set the size of cachecow
        :param size:
        :return:
        """
        raise RuntimeWarning("deprecated")
        assert isinstance(size, int), "size can only be an integer"
        self.cache_size = size

    def num_of_req(self):
        """
        return the number of requests in the trace
        :return:
        """
        if self.n_req == -1:
            self.n_req = self.reader.get_num_of_req()
        return self.n_req

    def num_of_uniq_req(self):
        """
        return the number of unique requests in the trace
        :return:
        """
        if self.n_uniq_req == -1:
            self.n_uniq_req = self.reader.get_num_of_uniq_req()
        return self.n_uniq_req

    def get_reuse_distance(self):
        """
        return an array of reuse distance
        :return:
        """
        return LRUProfiler(self.reader).get_reuse_distance()

    def get_hit_ratio_dict(self, algorithm, cache_size=-1, cache_params=None, bin_size=-1,
                      use_general_profiler=False, **kwargs):
        """
        return an dict of hit ratio of given algorithms, mapping from cache_size -> hit ratio
        :return:
        """
        hit_ratio_dict = {}
        p = self.profiler(algorithm, cache_params=cache_params,
                          cache_size=cache_size, bin_size=bin_size,
                          use_general_profiler=use_general_profiler, **kwargs)
        hr = p.get_hit_ratio(cache_size=cache_size)
        if isinstance(p, LRUProfiler):
            for i in range(len(hr)-2):
                hit_ratio_dict[i] = hr[i]
        elif isinstance(p, cGeneralProfiler) or isinstance(p, generalProfiler):
            for i in range(len(hr)):
                hit_ratio_dict[i * p.bin_size] = hr[i]
        return hit_ratio_dict

    def reset(self):
        """
        reset reader to the beginning of the trace
        :return:
        """
        assert self.reader is not None, "reader is None, cannot reset"
        self.reader.reset()

    def _profiler_pre_check(self, **kwargs):
        """
        check whether user has provided new cache size and data information
        :param kwargs:
        :return:
        """
        reader = None

        if 'num_of_threads' in kwargs:
            num_of_threads = kwargs['num_of_threads']
        elif 'num_of_thread' in kwargs:
            num_of_threads = kwargs['num_of_thread']
        else:
            num_of_threads = DEFAULT_NUM_OF_THREADS

        if 'data' in kwargs and 'dataType' in kwargs:
            if kwargs['dataType'] == 'plain':
                reader = plainReader(kwargs['data'])
            if kwargs['dataType'] == 'csv':
                assert 'column' in kwargs, "you didn't provide column number for csv reader"
                reader = csvReader(kwargs['data'], kwargs['column'])
            if kwargs['dataType'] == 'vscsi':
                reader = vscsiReader(kwargs['data'])
        elif 'reader' in kwargs:
            reader = kwargs['reader']
        else:
            reader = self.reader

        assert reader is not None, "you didn't provide a reader nor data (data file and data type)"
        self.reader = reader

        return reader, num_of_threads

    def heatmap(self, mode, plot_type, time_interval=-1, num_of_pixels=-1,
                algorithm="LRU", cache_params=None, cache_size=-1, **kwargs):
        """

        :param cache_size:
        :param cache_params:
        :param algorithm:
        :param num_of_pixels:
        :param time_interval:
        :param plot_type:
        :param mode:
        :param kwargs: algorithm:
        :return:
        """

        reader, num_of_threads = self._profiler_pre_check(**kwargs)
        assert cache_size <= self.num_of_req(), \
                    "you cannot specify cache size({}) larger than " \
                    "trace length({})".format(cache_size, self.num_of_req())

        l = ["avg_rd_start_time_end_time", "hit_ratio_start_time_cache_size"]

        if plot_type in l:
            hm = heatmap()
        else:
            if algorithm.lower() in c_available_cache:
                hm = cHeatmap()

            else:
                hm = heatmap()

        hm.heatmap(reader, mode, plot_type,
                   time_interval=time_interval,
                   num_of_pixels=num_of_pixels,
                   cache_size=cache_size,
                   algorithm=cache_alg_mapping[algorithm.lower()],
                   cache_params=cache_params,
                   **kwargs)

    def diffHeatmap(self, mode, plot_type, algorithm1, time_interval=-1, num_of_pixels=-1,
                    algorithm2="Optimal", cache_params1=None, cache_params2=None, cache_size=-1, **kwargs):
        """
        alg2 - alg1
        :param cache_size:
        :param cache_params2:
        :param cache_params1:
        :param algorithm2:
        :param num_of_pixels:
        :param time_interval:
        :param algorithm1:
        :param mode:
        :param plot_type:
        :param kwargs:
        :return:
        """
        figname = 'differential_heatmap.png'
        if 'figname' in kwargs:
            figname = kwargs['figname']

        assert cache_size != -1, "you didn't provide size for cache"
        assert cache_size <= self.num_of_req(), \
                    "you cannot specify cache size({}) larger than " \
                    "trace length({})".format(cache_size, self.num_of_req())

        reader, num_of_threads = self._profiler_pre_check(**kwargs)

        if algorithm1.lower() in c_available_cache and algorithm2.lower() in c_available_cache:
            hm = cHeatmap()
            hm.diffHeatmap(reader, mode, plot_type,
                           cache_size=cache_size,
                           time_interval=time_interval,
                           num_of_pixels=num_of_pixels,
                           algorithm1=cache_alg_mapping[algorithm1.lower()],
                           algorithm2=cache_alg_mapping[algorithm2.lower()],
                           cache_params1=cache_params1,
                           cache_params2=cache_params2,
                           **kwargs)

        else:
            hm = heatmap()
            if algorithm1.lower() not in c_available_cache:
                xydict1 = hm.calculate_heatmap_dat(reader, mode, plot_type,
                                                   time_interval=time_interval,
                                                   cache_size=cache_size,
                                                   algorithm=algorithm1,
                                                   cache_params=cache_params1,
                                                   **kwargs)[0]
            else:
                xydict1 = c_heatmap.heatmap(reader.cReader, mode, plot_type,
                                            cache_size=cache_size,
                                            time_interval=time_interval,
                                            algorithm=algorithm1,
                                            cache_params=cache_params1,
                                            num_of_threads=num_of_threads)

            if algorithm2.lower() not in c_available_cache:
                xydict2 = hm.calculate_heatmap_dat(reader, mode, plot_type,
                                                   time_interval=time_interval,
                                                   cache_size=cache_size,
                                                   algorithm=algorithm2,
                                                   cache_params=cache_params2,
                                                   **kwargs)[0]
            else:
                xydict2 = c_heatmap.heatmap(reader.cReader, mode, plot_type,
                                            time_interval=time_interval,
                                            cache_size=cache_size,
                                            algorithm=algorithm2,
                                            cache_params=cache_params2,
                                            num_of_threads=num_of_threads)

            cHm = cHeatmap()
            text = "      differential heatmap\n      cache size: {},\n      cache type: ({}-{})/{},\n" \
                   "      time type: {},\n      time interval: {},\n      plot type: \n{}".format(
                cache_size, algorithm2, algorithm1, algorithm1, mode, time_interval, plot_type)

            x1, y1 = xydict1.shape
            x1 = int(x1 / 2.8)
            y1 /= 8
            if mode == 'r':
                time_mode_string = "real"
            elif mode == "v":
                time_mode_string = "virtual"
            else:
                raise RuntimeError("unknown time mode {}".format(mode))

            cHm.setPlotParams('x', '{}_time'.format(time_mode_string), xydict=xydict1,
                              label='start time ({})'.format(time_mode_string),
                              text=(x1, y1, text))
            cHm.setPlotParams('y', '{}_time'.format(time_mode_string), xydict=xydict1,
                              label='end time ({})'.format(time_mode_string),
                              fixed_range=(-1, 1))
            np.seterr(divide='ignore', invalid='ignore')

            plot_dict = (xydict2 - xydict1) / xydict1
            cHm.draw_heatmap(plot_dict, figname=figname)

    def profiler(self, algorithm, cache_params=None, cache_size=-1, bin_size=-1,
                 use_general_profiler=False, **kwargs):
        """
        profiler
        :param cache_size:
        :param cache_params:
        :param algorithm:
        :param use_general_profiler: for LRU only, if it is true, then return a cGeneralProfiler for LRU,
                                        otherwise, return a LRUProfiler for LRU
                                        Note: LRUProfiler does not require cache_size/bin_size params,
                                        it does not sample thus provides a smooth curve, however, it is O(logN) at each step,
                                        in constrast, cGeneralProfiler samples the curve, but use O(1) at each step
        :param kwargs:
        :return:
        """

        reader, num_of_threads = self._profiler_pre_check(**kwargs)

        profiler = None

        if algorithm.lower() == "lru" and not use_general_profiler:
            profiler = LRUProfiler(reader, cache_size, cache_params)
        else:
            assert cache_size != -1, "you didn't provide size for cache"
            assert cache_size <= self.num_of_req(), "you cannot specify cache size({}) " \
                                                        "larger than trace length({})".format(cache_size,
                                                                                              self.num_of_req())
            if isinstance(algorithm, str):
                if algorithm.lower() in c_available_cache:
                    profiler = cGeneralProfiler(reader, cache_alg_mapping[algorithm.lower()],
                                                cache_size, bin_size,
                                                cache_params, num_of_threads)
                else:
                    profiler = generalProfiler(reader, self.cacheclass_mapping[algorithm.lower()],
                                               cache_size, bin_size,
                                               cache_params, num_of_threads)
            else:
                profiler = generalProfiler(reader, algorithm, cache_size, bin_size,
                                           cache_params, num_of_threads)

        return profiler

    def twoDPlot(self, plot_type, **kwargs):
        """
        two dimensional plots
        :param plot_type:
        :param kwargs:
        :return:
        """
        kwargs["figname"] = kwargs.get("figname", "{}.png".format(plot_type))

        if plot_type == 'cold_miss' or plot_type == "cold_miss_count":
            if plot_type == 'cold_miss':
                print("please use cold_miss_count, cold_miss is deprecated")
            assert "mode" in kwargs or "time_mode" in kwargs, \
                "you need to provide time_mode (r/v) for plotting cold_miss2d"
            assert "time_interval" in kwargs, \
                "you need to provide time_interval for plotting cold_miss2d"
            return cold_miss_count_2d(self.reader, **kwargs)

        elif plot_type == 'cold_miss_ratio':
            assert "mode" in kwargs or "time_mode" in kwargs, \
                "you need to provide time_mode (r/v) for plotting cold_miss2d"
            assert "time_interval" in kwargs, \
                "you need to provide time_interval for plotting cold_miss2d"
            return cold_miss_ratio_2d(self.reader, **kwargs)

        elif plot_type == "request_rate":
            assert "mode" in kwargs or "time_mode" in kwargs, \
                "you need to provide time_mode (r/v) for plotting request_rate2d"
            assert "time_interval" in kwargs, \
                "you need to provide time_interval for plotting request_num2d"
            return request_rate_2d(self.reader, **kwargs)

        elif plot_type == "popularity":
            return popularity_2d(self.reader, **kwargs)

        elif plot_type == "rd_popularity":
            return rd_popularity_2d(self.reader, **kwargs)

        elif plot_type == "rt_popularity":
            return rt_popularity_2d(self.reader, **kwargs)

        elif plot_type == 'mapping':
            namemapping_2d(self.reader, **kwargs)

        elif plot_type == "interval_hit_ratio":
            assert "cache_size" in kwargs, "please provide cache size for interval hit ratio curve plotting"
            return interval_hit_ratio_2d(self.reader, **kwargs)

        else:
            WARNING("currently don't support your specified plot_type: " + str(plot_type))

    def evictionPlot(self, mode, time_interval, plot_type, algorithm, cache_size, cache_params=None, **kwargs):
        """
        plot eviction stat vs time, currently support
        reuse_dist, freq, accumulative_freq
        :param mode:
        :param time_interval:
        :param plot_type:
        :param algorithm:
        :param cache_size:
        :param cache_params:
        :param kwargs:
        :return:
        """
        if plot_type == "reuse_dist":
            eviction_stat_reuse_dist_plot(self.reader, algorithm, cache_size, mode,
                                          time_interval, cache_params=cache_params, **kwargs)
        elif plot_type == "freq":
            eviction_stat_freq_plot(self.reader, algorithm, cache_size, mode, time_interval,
                                    accumulative=False, cache_params=cache_params, **kwargs)

        elif plot_type == "accumulative_freq":
            eviction_stat_freq_plot(self.reader, algorithm, cache_size, mode, time_interval,
                                    accumulative=True, cache_params=cache_params, **kwargs)
        else:
            print("the plot type you specified is not supported: {}, currently only support: {}".format(
                plot_type, "reuse_dist, freq, accumulative_freq"
            ))

    def plotHRCs(self, algorithm_list, cache_params=(),
                 cache_size=-1, bin_size=-1,
                 auto_size=True, figname="HRC.png", **kwargs):
        """

        :param algorithm_list:
        :param cache_params:
        :param cache_size:
        :param bin_size:
        :param auto_size:
        :param figname:
        :param kwargs: block_unit_size, num_of_threads, label, autosize_threshold, xlimit, ylimit, cache_unit_size

        :return:
        """

        plot_dict = prepPlotParams("Hit Ratio Curve", "Cache Size (Items)", "Hit Ratio", figname, **kwargs)
        hit_ratio_dict = {}

        num_of_threads          =       kwargs.get("num_of_threads",        os.cpu_count())
        cache_unit_size         =       kwargs.get("cache_unit_size",       0)
        use_general_profiler    =       kwargs.get("use_general_profiler",  False)
        save_gradually          =       kwargs.get("save_gradually",        False)
        threshold               =       kwargs.get('autosize_threshold',    0.98)
        label                   =       kwargs.get("label",                 algorithm_list)

        profiling_with_size = False
        LRU_HR = None

        if cache_size == -1 and auto_size:
            LRU_HR = LRUProfiler(self.reader).plotHRC(auto_resize=True, threshold=threshold, no_save=True)
            cache_size = len(LRU_HR)
        else:
            assert cache_size < self.num_of_req(), "you cannot specify cache size larger than trace length"

        if bin_size == -1:
            bin_size = cache_size // DEFAULT_BIN_NUM_PROFILER + 1

        # check whether profiling with size
        block_unit_size = 0
        for i in range(len(algorithm_list)):
            if i < len(cache_params) and cache_params[i]:
                block_unit_size = cache_params[i].get("block_unit_size", 0)
                if block_unit_size != 0:
                    profiling_with_size = True
                    break
        if profiling_with_size and cache_unit_size != 0 and block_unit_size != cache_unit_size:
            raise RuntimeError("cache_unit_size and block_unit_size is not equal {} {}".\
                                format(cache_unit_size, block_unit_size))


        for i in range(len(algorithm_list)):
            alg = algorithm_list[i]
            if cache_params and i < len(cache_params):
                cache_param = cache_params[i]
                if profiling_with_size:
                    if cache_param is None or 'block_unit_size' not in cache_param:
                        ERROR("it seems you want to profiling with size, "
                              "but you didn't provide block_unit_size in "
                              "cache params {}".format(cache_param))
                    elif cache_param["block_unit_size"] != block_unit_size:
                        ERROR("only same block unit size for single plot is allowed")

            else:
                cache_param = None
            profiler = self.profiler(alg, cache_param, cache_size, bin_size=bin_size,
                                     use_general_profiler=use_general_profiler,
                                     num_of_threads=num_of_threads)
            t1 = time.time()

            if alg == "LRU":
                if LRU_HR is None:  # no auto_resize
                    hr = profiler.get_hit_ratio()
                    if use_general_profiler:
                        # save the computed hit ratio
                        hit_ratio_dict["LRU"] = {}
                        for j in range(len(hr)):
                            hit_ratio_dict["LRU"][j * bin_size] = hr[j]
                        plt.plot([j * bin_size for j in range(len(hr))], hr, label=label[i])
                    else:
                        # save the computed hit ratio
                        hit_ratio_dict["LRU"] = {}
                        for j in range(len(hr)-2):
                            hit_ratio_dict["LRU"][j] = hr[j]
                        plt.plot(hr[:-2], label=label[i])
                else:
                    # save the computed hit ratio
                    hit_ratio_dict["LRU"] = {}
                    for j in range(len(LRU_HR)):
                        hit_ratio_dict["LRU"][j] = LRU_HR[j]
                    plt.plot(LRU_HR, label=label[i])
            else:
                hr = profiler.get_hit_ratio()
                # save the computed hit ratio
                hit_ratio_dict[alg] = {}
                for j in range(len(hr)):
                    hit_ratio_dict[alg][j * bin_size] = hr[j]
                plt.plot([j * bin_size for j in range(len(hr))], hr, label=label[i])
            self.reader.reset()
            INFO("HRC plotting {} computation finished using time {} s".format(alg, time.time() - t1))
            if save_gradually:
                plt.savefig(plot_dict['figname'], dpi=600)

        plt.legend(loc="best")
        plt.xlabel(plot_dict['xlabel'])
        plt.ylabel(plot_dict['ylabel'])
        plt.title(plot_dict['title'], fontsize=18, color='black')

        if "xlimit" in kwargs:
            plt.xlim(kwargs["xlimit"])
        if "ylimit" in kwargs:
            plt.ylim(kwargs["ylimit"])

        if cache_unit_size != 0:
            plt.xlabel("Cache Size (MB)")
            plt.gca().xaxis.set_major_formatter(
                FuncFormatter(lambda x, p: int(x * cache_unit_size // 1024 // 1024)))

        if not 'no_save' in kwargs or not kwargs['no_save']:
            plt.savefig(plot_dict['figname'], dpi=600)
        INFO("HRC plot is saved")
        try:
            plt.show()
        except:
            pass
        plt.clf()
        return hit_ratio_dict

    def plotMRCs(self, algorithm_list, cache_params=None, cache_size=-1, bin_size=-1, auto_size=True, **kwargs):
        """
        plot MRCs, not updated, might be deprecated
        :param algorithm_list:
        :param cache_params:
        :param cache_size:
        :param bin_size:
        :param auto_size:
        :param kwargs:
        :return:
        """
        raise RuntimeWarning("deprecated")
        plot_dict = prepPlotParams("Miss Ratio Curve", "Cache Size(item)", "Miss Ratio", "MRC.png", **kwargs)
        num_of_threads = 4
        if 'num_of_threads' in kwargs:
            num_of_threads = kwargs['num_of_threads']
        if 'label' not in kwargs:
            label = algorithm_list
        else:
            label = kwargs['label']

        threshold = 0.98
        if 'autosize_threshold' in kwargs:
            threshold = kwargs['autosize_threshold']

        ymin = 1

        if auto_size:
            cache_size = LRUProfiler(self.reader).plotMRC(auto_resize=True, threshold=threshold, no_save=True)
        else:
            assert cache_size < self.num_of_req(), "you cannot specify cache size larger than trace length"

        if bin_size == -1:
            bin_size = cache_size // DEFAULT_BIN_NUM_PROFILER + 1
        for i in range(len(algorithm_list)):
            alg = algorithm_list[i]
            if cache_params and i < len(cache_params):
                cache_param = cache_params[i]
            else:
                cache_param = None
            profiler = self.profiler(alg, cache_param, cache_size,
                                     bin_size=bin_size, num_of_threads=num_of_threads)
            mr = profiler.get_miss_rate()
            ymin = min(ymin, max(min(mr) - 0.02, 0))
            self.reader.reset()
            # plt.xlim(0, cache_size)
            if alg != "LRU":
                plt.plot([i * bin_size for i in range(len(mr))], mr, label=label[i])
            else:
                plt.plot(mr[:-2], label=label[i])

        print("ymin = {}".format(ymin))
        if "ymin" in kwargs:
            ymin = kwargs['ymin']

        plt.ylim(ymin=ymin)
        plt.semilogy()
        plt.legend(loc="best")
        plt.xlabel(plot_dict['xlabel'])
        plt.ylabel(plot_dict['ylabel'])
        plt.title(plot_dict['title'], fontsize=18, color='black')
        if not 'no_save' in kwargs or not kwargs['no_save']:
            plt.savefig(plot_dict['figname'], dpi=600)
        INFO("plot is saved at the same directory")
        try:
            plt.show()
        except:
            pass
        plt.clf()

    def characterize(self, type, cache_size=-1):
        # TODO: jason: allow one single function call to obtain the most useful information
        # and would be better to give time estimation while running

        supported_types = ["short", "medium", "long", "all"]
        if type not in supported_types:
            WARNING("unknown type {}, supported types: {}".format(type, supported_types))
            return

        INFO("trace information ")
        trace_stat = traceStat(self.reader)
        print(trace_stat)
        if cache_size == -1:
            cache_size = trace_stat.num_of_uniq_obj//100

        if type == "short":
            # short should support [basic stat, HRC of LRU, OPT, cold miss ratio, popularity]
            INFO("now begin to plot cold miss ratio curve")
            self.twoDPlot("cold_miss_ratio", mode="v", time_interval=trace_stat.num_of_requests//100)

            INFO("now begin to plot popularity curve")
            self.twoDPlot("popularity")

            INFO("now begin to plot hit ratio curves")
            self.plotHRCs(["LRU", "Optimal"], cache_size=cache_size, bin_size=cache_size//cpu_count()+1,
                          num_of_threads=cpu_count(),
                          use_general_profiler=True, save_gradually=True)

        elif type == "medium":
            # medium should support [
            if trace_stat.time_span != 0:
                INFO("now begin to plot request rate curve")
                self.twoDPlot("request_rate", mode="r", time_interval=trace_stat.time_span//100)

            INFO("now begin to plot cold miss ratio curve")
            self.twoDPlot("cold_miss_ratio", mode="v", time_interval=trace_stat.num_of_requests//100)

            INFO("now begin to plot popularity curve")
            self.twoDPlot("popularity")

            INFO("now begin to plot mapping plot")
            self.twoDPlot("mapping")

            INFO("now begin to plot hit ratio curves")
            self.plotHRCs(["LRU", "Optimal", "LFU"], cache_size=cache_size,
                          bin_size=cache_size//cpu_count()//4+1,
                          num_of_threads=cpu_count(),
                          use_general_profiler=True, save_gradually=True)


        elif type == "long":
            if trace_stat.time_span != 0:
                INFO("now begin to plot request rate curve")
                self.twoDPlot("request_rate", mode="r", time_interval=trace_stat.time_span//100)

            INFO("now begin to plot cold miss ratio curve")
            self.twoDPlot("cold_miss_ratio", mode="v", time_interval=trace_stat.num_of_requests//100)

            INFO("now begin to plot popularity curve")
            self.twoDPlot("popularity")

            INFO("now begin to plot rd distribution popularity")
            self.twoDPlot("rd_distribution")

            INFO("now begin to plot mapping plot")
            self.twoDPlot("mapping")

            INFO("now begin to plot rd distribution heatmap")
            self.heatmap("v", "rd_distribution", time_interval=trace_stat.num_of_requests//100)


            INFO("now begin to plot hit ratio curves")
            self.plotHRCs(["LRU", "Optimal", "LFU", "ARC"], cache_size=cache_size,
                          bin_size=cache_size//cpu_count()//16+1,
                          num_of_threads=cpu_count(),
                          save_gradually=True)

            INFO("now begin to plot hit_ratio_start_time_end_time heatmap")
            self.heatmap("v", "hit_ratio_start_time_end_time",
                         time_interval=trace_stat.num_of_requests//100,
                         cache_size=cache_size)


        elif type == "all":
            if trace_stat.time_span != 0:
                INFO("now begin to plot request rate curve")
                self.twoDPlot("request_rate", mode="r", time_interval=trace_stat.time_span//200)

            INFO("now begin to plot cold miss ratio curve")
            self.twoDPlot("cold_miss_ratio", mode="v", time_interval=trace_stat.num_of_requests//200)

            INFO("now begin to plot popularity curve")
            self.twoDPlot("popularity")

            INFO("now begin to plot rd distribution popularity")
            self.twoDPlot("rd_distribution")

            INFO("now begin to plot mapping plot")
            self.twoDPlot("mapping")

            INFO("now begin to plot rd distribution heatmap")
            self.heatmap("v", "rd_distribution", time_interval=trace_stat.num_of_requests//200)


            INFO("now begin to plot hit ratio curves")
            self.plotHRCs(["LRU", "Optimal", "LFU", "ARC"], cache_size=cache_size,
                          bin_size=cache_size//cpu_count()//60+1,
                          num_of_threads=cpu_count(),
                          save_gradually=True)

            INFO("now begin to plot hit_ratio_start_time_end_time heatmap")
            self.heatmap("v", "hit_ratio_start_time_end_time",
                         time_interval=trace_stat.num_of_requests//200,
                         cache_size=cache_size)


    def stat(self):
        assert self.reader, "you haven't provided a data file"
        return traceStat(self.reader).get_stat()

    def __len__(self):
        assert self.reader, "you haven't provided a data file"
        return len(self.reader)

    def __iter__(self):
        assert self.reader, "you haven't provided a data file"
        return self.reader

    def next(self):
        return self.__next__()

    def __next__(self):  # Python 3
        return self.reader.next()

    def __del__(self):
        self.close()

    def close(self):
        """
        close the reader opened in cachecow, and clean up in the future
        :return:
        """
        if self.reader is not None:
            self.reader.close()
            self.reader = None
